using EFT;
using EFT.CameraControl;
using UnityEngine;
using UnityEngine.Rendering;

namespace UstAchae.PVS22
{
    // Live 1x picture (night vision, or thermal for clip-ons with a "clipon_thermal" marker) on the eyepiece: the
    // prefab's "pvs22_live" disc with our own lens shader (UstAchae/PVS22/Eyepiece, depth-tested: the game's own
    // lens shader draws over everything in front of it, the shooter's head included, and its eye-relief masks drew
    // shadows and rings). As in the real device, the picture is what the objective sees, shown 1x at infinity: a
    // private camera at the front of the objective (so nothing behind it, such as the sight behind or the clip-on
    // itself, can show; parts of the weapon ahead of it can), aimed like a window, along the directions from the
    // eye through each point of the lens (an off-centre frustum), so the view through the lens shifts as the eye
    // moves, then turned into the tube picture. The whole picture fades out evenly once the eye's line to the lens
    // centre is beyond half the device's field of view (no partial crescents at the rim, the user's choice), and
    // the eyepiece is not drawn while a player's body sits between it and the camera (a free or third-person
    // camera behind the shooter's head, which does not hide it by depth). Used aiming or not; the clip-on's sight
    // lens, fed by the game's optic camera, stays hidden.
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
        const float Visible = 0.5f;             // the picture spans the lens exactly (its uv 0..1)

        static Camera liveCamera;
        static RenderTexture raw, picture;
        static Material process;
        static bool rendering;
        static int renderedFrame = -1;
        static readonly int pictureId = Shader.PropertyToID("_PVS22Picture");
        static readonly int onId = Shader.PropertyToID("_PVS22On");
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
        float halfField;  // degrees
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
            lens.halfField = ImageProfile.For(clipOn).Fov * 0.5f;
            // This disc is the eyepiece on a weapon (picture or dark lens), aiming or not: the sight lens and the dark
            // glass behind it are never needed there.
            foreach (string hidden in new[] { SightLensNode, BackGlassNode })
            {
                Renderer r = clipOn.Find(hidden)?.GetComponent<Renderer>();
                if (r != null) r.forceRenderingOff = true;
            }
            lens.body = clipOn.Find(BodyNode);
            Mesh mesh = lens.body != null ? lens.body.GetComponent<MeshFilter>()?.sharedMesh : null;
            if (mesh != null) lens.bodyBounds = mesh.bounds;
        }

        // Not drawn while a player's body is between the main camera and the eyepiece: seen from a free or
        // third-person camera behind the shooter, the head does not hide it by depth. In first person the camera is
        // inside the head's collider, which a ray from there does not hit.
        void LateUpdate()
        {
            Camera main = Camera.main;
            if (disc == null || main == null) return;
            Vector3 from = main.transform.position, to = transform.position - from;
            bool blocked = false;
            foreach (RaycastHit hit in Physics.RaycastAll(from, to.normalized, to.magnitude - 0.01f, ~0, QueryTriggerInteraction.Ignore))
                if (hit.collider.GetComponentInParent<Player>() != null) { blocked = true; break; }
            disc.forceRenderingOff = blocked;
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
            // The whole picture fades as the eye's line to the lens centre leaves the field of view.
            Vector3 axis = -transform.up, toLens = transform.position - eye.transform.position;
            float offAxis = Vector3.Angle(toLens, axis);
            float shown = on ? 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(halfField - 1f, halfField, offAxis)) : 0f;
            disc.GetPropertyBlock(block);
            block.SetFloat(onId, shown);
            if (on) block.SetTexture(pictureId, picture);
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
            // The picture's corners, beyond the lens's edge, are black too.
            process.SetFloat(lensId, Visible);
            TubeEffect.SetGlobals(gain, noise, grain * size * 2f * Visible / Mathf.Max(lensPixels, 1f), profile.Phosphor);
            Shader.SetGlobalVector(thermalParamsId, new Vector4(PVS22Plugin.ThermalLevel, PVS22Plugin.ThermalGain, 0f, 0f));
            process.SetFloat(thermalId, thermal ? 1f : 0f);
            Graphics.Blit(raw, picture, process);
            return true;
        }
    }
}
