using EFT.CameraControl;
using UnityEngine;
using UnityEngine.Rendering;

namespace UstAchae.PVS22
{
    // Live 1x picture (night vision, or thermal for clip-ons with a "clipon_thermal" marker) on the eyepiece for
    // when no optic camera feeds the sight lens: behind a red dot or a holographic sight, or not aiming at all.
    // The prefab's "pvs22_live" disc carries the game's own lens material (CW FX/OpticSight, the one every
    // native scope uses) for the native lens and dark idle look. That shader shows the global _CamTex, the optic
    // camera's picture; this disc gets its own instead, per renderer. As in the real device, the picture is what
    // the objective sees, shown 1x at infinity: a private camera at the front of the objective (so nothing behind
    // it, such as the sight behind or the clip-on itself, can show; parts of the weapon ahead of it can), aimed
    // like a window, along the directions from the eye through each point of the lens (an off-centre frustum),
    // so the view through the lens shifts as the eye moves, black where that direction is beyond half the
    // device's field of view (its field stop), then turned into the tube picture. The native mask's slide with
    // the eye is turned off: it models a scope's exit pupil at its eye relief, and from the distance this
    // eyepiece is seen at it only drew a large round shadow. The same disc is used when aiming through the
    // clip-on itself; its sight lens, fed by the game's optic camera with that mask, stays hidden.
    class LiveLens : MonoBehaviour
    {
        const string LiveNode = "pvs22_live";
        const string FrontMarker = "pvs22_front";
        const string RearMarker = "pvs22_rear";
        const string ThermalMarker = "clipon_thermal";
        const string SightLensNode = "linza";
        const string BackGlassNode = "eyepiece_glass";
        const string BodyNode = "an_pvs22_LOD0";
        const float MaxEyeDistance = 1.0f;      // the shooter's own clip-on, not ones seen on other weapons
        // How far a scope's OpticSight node may sit off the clip-on's axis and still count as behind it: the node
        // is the scope's "mode" object, often at the mount origin a few cm below the optic axis.
        const float AxisTolerance = 0.10f;
        const float MaxBehind = 0.6f;
        const float DiscRadius = 0.016539544f;  // the lens disc mesh's radius; its node is scaled to the lens
        const float Off = 0.97f;                // _SwitchToSight of a native sight that is not in use
        // Native lens settings for this eyepiece: _Scales.x 10 shows _CamTex out to 0.47 of its width from the centre
        // with a soft native rim (measured); _Shifts zero stops the mask sliding with the eye.
        static readonly Vector4 Scales = new Vector4(10f, 100f, 100f, 100f);
        const float Visible = 0.47f;

        static Camera liveCamera;
        static RenderTexture raw, picture;
        static Material process;
        static bool rendering;
        static int renderedFrame = -1;
        static readonly int camTexId = Shader.PropertyToID("_CamTex");
        static readonly int switchId = Shader.PropertyToID("_SwitchToSight");
        static readonly int scalesId = Shader.PropertyToID("_Scales");
        static readonly int shiftsId = Shader.PropertyToID("_Shifts");
        static readonly int fieldId = Shader.PropertyToID("_PVS22Field");
        static readonly int fieldTanId = Shader.PropertyToID("_PVS22FieldTan");
        static readonly int lensId = Shader.PropertyToID("_PVS22Lens");
        static readonly int thermalId = Shader.PropertyToID("_PVS22Thermal");
        static readonly int thermalParamsId = Shader.PropertyToID("_PVS22ThermalParams");
        // Set by EFT's ThermalVision around its camera's render: materials then write their heat into GBuffer0.
        static readonly int thermalOnId = Shader.PropertyToID("_ThermalVisionOn");
        static CommandBuffer copyHeat;

        Renderer disc;
        Transform clipOn, front, rear, body;
        Bounds bodyBounds;
        MaterialPropertyBlock block;
        bool thermal;
        bool scopeBehind;
        float checkedAt = -10f;

        public static void Attach(Transform clipOn)
        {
            Transform node = clipOn.Find(LiveNode);
            if (node == null || node.GetComponent<LiveLens>() != null) return;
            LiveLens lens = node.gameObject.AddComponent<LiveLens>();
            lens.disc = node.GetComponent<Renderer>();
            lens.clipOn = clipOn;
            lens.front = clipOn.Find(FrontMarker);
            lens.rear = clipOn.Find(RearMarker);
            lens.block = new MaterialPropertyBlock();
            lens.thermal = clipOn.Find(ThermalMarker) != null;
            // This disc is the eyepiece on a weapon (picture or dark lens), aiming or not: the sight lens and the dark
            // glass behind it are never needed there.
            foreach (string hidden in new[] { SightLensNode, BackGlassNode })
            {
                Renderer r = clipOn.Find(hidden)?.GetComponent<Renderer>();
                if (r != null) r.forceRenderingOff = true;
            }
            lens.body = clipOn.Find(BodyNode);
            Mesh mesh = lens.body != null ? lens.body.GetComponent<MeshFilter>()?.sharedMesh : null;
            if (mesh != null)
            {
                lens.bodyBounds = mesh.bounds;
                lens.ToOpening(mesh);
            }
        }

        // The native lens shader draws its picture over everything (ZTest Always), which is fine for a native
        // scope whose lens sits at the end of the eyepiece but painted the eyepiece's recessed lens over the boot
        // or eyecup in front of it. So the disc goes where a native scope has its lens: just inside the eyepiece
        // opening, with nothing of the clip-on in front of it. It keeps its size: the shader's mask edge has the
        // lens's size, and an enlarged disc showed it as a dark ring inside the lens with picture outside it. Runs
        // before the placement rig records the children's positions. A lens within 3 mm of the opening, or wider
        // than it, stays where it is.
        void ToOpening(Mesh mesh)
        {
            Vector3 centre = transform.localPosition - body.localPosition;  // the axis, in the body mesh's frame
            float lensRadius = DiscRadius * transform.localScale.x, reach = lensRadius * 2.5f;
            Vector3[] vertices = mesh.vertices;
            float rearZ = float.MaxValue;
            foreach (Vector3 v in vertices)
                if (new Vector2(v.x - centre.x, v.y - centre.y).magnitude < reach) rearZ = Mathf.Min(rearZ, v.z);
            if (centre.z - rearZ < 0.003f) return;
            float opening = float.MaxValue;  // the rim's inner edge: the closest point to the axis near the end
            foreach (Vector3 v in vertices)
            {
                if (v.z > rearZ + 0.003f) continue;
                float r = new Vector2(v.x - centre.x, v.y - centre.y).magnitude;
                if (r < reach) opening = Mathf.Min(opening, r);
            }
            if (opening < lensRadius || opening == float.MaxValue) return;
            Vector3 local = transform.localPosition;
            transform.localPosition = new Vector3(local.x, local.y, body.localPosition.z + rearZ + 0.0005f);
        }

        void OnWillRenderObject()
        {
            Camera eye = Camera.current;
            if (rendering || eye == null || front == null || rear == null) return;
            bool player = eye == Camera.main;

            // On for the shooter's own clip-on, aiming or not (user's choice), unless a magnified scope sits
            // behind it: that scope's camera draws the picture when aiming, and the scope hides the eyepiece
            // otherwise, so the extra render would be wasted. Other weapons' clip-ons and other cameras show the
            // native dark lens of a sight not in use.
            if (Time.unscaledTime - checkedAt > 0.5f)
            {
                scopeBehind = ScopeBehind();
                checkedAt = Time.unscaledTime;
            }
            bool on = !scopeBehind && player && (eye.transform.position - transform.position).sqrMagnitude < MaxEyeDistance * MaxEyeDistance;
            // Every other frame (about 30 Hz at 60 fps, close to a tube's own refresh): halves the extra render's cost.
            if (on && Time.frameCount - renderedFrame >= 2 && Render(eye)) renderedFrame = Time.frameCount;
            on &= picture != null;
            disc.GetPropertyBlock(block);
            block.SetFloat(switchId, on ? 0f : Off);
            block.SetVector(scalesId, Scales);
            block.SetVector(shiftsId, Vector4.zero);
            if (on) block.SetTexture(camTexId, picture);
            disc.SetPropertyBlock(block);
        }

        // A magnified optic (an OpticSight, which red dots and holographic sights lack) on the same weapon,
        // behind the clip-on's rear end and near its axis. Judged in the clip-on's own frame, where +Z points to
        // the muzzle (the placement uses the same frame); the front/rear markers are not reliably front and back.
        bool ScopeBehind()
        {
            Transform root = clipOn.GetComponentInParent<WeaponPrefab>()?.transform ?? clipOn.root;
            Vector3 a = clipOn.InverseTransformPoint(front.position), b = clipOn.InverseTransformPoint(rear.position);
            float rearZ = Mathf.Min(a.z, b.z), axisY = (a.y + b.y) / 2f;
            foreach (OpticSight sight in root.GetComponentsInChildren<OpticSight>())
            {
                if (sight.transform.IsChildOf(clipOn)) continue;
                Vector3 p = clipOn.InverseTransformPoint(sight.transform.position);
                float behind = rearZ - p.z;
                if (behind > 0f && behind < MaxBehind && new Vector2(p.x, p.y - axisY).magnitude < AxisTolerance) return true;
            }
            return false;
        }

        bool Render(Camera eye)
        {
            if (process == null)
            {
                Shader shader = TubeEffect.ShaderOf(clipOn);
                if (shader == null) return false;
                process = new Material(shader) { hideFlags = HideFlags.DontSave };
            }
            if (liveCamera == null)
            {
                var go = new GameObject("PVS22 live camera");
                DontDestroyOnLoad(go);
                liveCamera = go.AddComponent<Camera>();
                liveCamera.enabled = false;
            }
            int size = Mathf.ClosestPowerOfTwo(Mathf.Clamp((int)(2048 * PVS22Plugin.LiveResolution), 256, 4096));
            if (raw == null || raw.width != size)
            {
                if (raw != null) { raw.Release(); picture.Release(); }
                raw = new RenderTexture(size, size, 24, RenderTextureFormat.ARGBHalf) { name = "PVS22 live" };
                picture = new RenderTexture(size, size, 0, RenderTextureFormat.ARGB32) { name = "PVS22 live picture" };
            }

            // At the front of the objective, looking down the clip-on's axis (the disc faces +Y toward the shooter),
            // with a frustum through the picture's extent on the lens plane as seen from the eye: the native lens maps
            // the picture onto the lens, so each lens point shows the scene along the eye's line through it.
            Vector3 p = eye.transform.position, axis = -transform.up;
            float distance = Vector3.Dot(transform.position - p, axis);
            if (distance < 0.02f) return false;
            float radius = DiscRadius * transform.lossyScale.x, span = radius * 0.5f / Visible;
            float ahead = Mathf.Max(Vector3.Dot(front.position - transform.position, axis), Vector3.Dot(rear.position - transform.position, axis));
            if (body != null)
            {
                Vector3 c = bodyBounds.center, e = bodyBounds.extents;
                for (int i = 0; i < 8; i++)
                {
                    Vector3 corner = body.TransformPoint(c + new Vector3((i & 1) == 0 ? -e.x : e.x, (i & 2) == 0 ? -e.y : e.y, (i & 4) == 0 ? -e.z : e.z));
                    ahead = Mathf.Max(ahead, Vector3.Dot(corner - transform.position, axis));
                }
            }
            Quaternion rotation = Quaternion.LookRotation(axis, clipOn.up);
            Vector3 toEye = p - transform.position;
            float ex = Vector3.Dot(toEye, rotation * Vector3.right), ey = Vector3.Dot(toEye, rotation * Vector3.up);
            const float near = 0.005f;
            float k = near / distance;
            liveCamera.CopyFrom(eye);
            liveCamera.targetTexture = raw;
            liveCamera.rect = new Rect(0f, 0f, 1f, 1f);
            liveCamera.transform.SetPositionAndRotation(transform.position + axis * (ahead + near), rotation);
            liveCamera.nearClipPlane = near;
            liveCamera.projectionMatrix = Matrix4x4.Frustum((-span - ex) * k, (span - ex) * k, (-span - ey) * k, (span - ey) * k, near, liveCamera.farClipPlane);

            // Thermal: render the scene the way EFT's ThermalVision does (heat flag on, GBuffer0 copied over the
            // lit image before transparents); the processing below maps that heat white-hot.
            if (thermal)
            {
                if (copyHeat == null)
                {
                    copyHeat = new CommandBuffer { name = "PVS22 copy heat" };
                    copyHeat.Blit(BuiltinRenderTextureType.GBuffer0, BuiltinRenderTextureType.CameraTarget);
                }
                liveCamera.AddCommandBuffer(CameraEvent.BeforeForwardAlpha, copyHeat);
                Shader.SetGlobalFloat(thermalOnId, 1f);
            }
            // No shadows in this small picture: their maps are redrawn for every camera and were most of its cost.
            float shadowDistance = QualitySettings.shadowDistance;
            QualitySettings.shadowDistance = 0f;
            rendering = true;
            try { liveCamera.Render(); }
            finally
            {
                rendering = false;
                QualitySettings.shadowDistance = shadowDistance;
                liveCamera.ResetProjectionMatrix();
                if (thermal)
                {
                    Shader.SetGlobalFloat(thermalOnId, 0f);
                    liveCamera.RemoveCommandBuffer(CameraEvent.BeforeForwardAlpha, copyHeat);
                }
            }

            // The same tube model as the optic-camera effect, at 1x (no over-magnification). Its grain is in pixels
            // of this picture, whose visible part spans only the lens: scaled to keep the grain's size on screen.
            ImageProfile profile = ImageProfile.For(clipOn);
            TubeEffect.Settings(profile, 1f, out float gain, out float noise, out float grain);
            float lensPixels = radius / distance / Mathf.Tan(eye.fieldOfView * 0.5f * Mathf.Deg2Rad) * eye.pixelHeight;
            // The field stop: black where the eye's line through the lens is beyond half the field of view.
            process.SetVector(fieldId, new Vector4(ex, ey, distance, span));
            process.SetFloat(fieldTanId, Mathf.Tan(profile.Fov * 0.5f * Mathf.Deg2Rad));
            // The picture beyond the lens's edge is black too: the native lens's soft rim samples a little past it,
            // and from the side that part could still be in the field and showed as a bright crescent at the rim.
            process.SetFloat(lensId, Visible);
            TubeEffect.SetGlobals(gain, noise, grain * size * 2f * Visible / Mathf.Max(lensPixels, 1f), profile.Phosphor);
            Shader.SetGlobalVector(thermalParamsId, new Vector4(PVS22Plugin.ThermalLevel, PVS22Plugin.ThermalGain, 0f, 0f));
            process.SetFloat(thermalId, thermal ? 1f : 0f);
            Graphics.Blit(raw, picture, process);
            return true;
        }
    }
}
