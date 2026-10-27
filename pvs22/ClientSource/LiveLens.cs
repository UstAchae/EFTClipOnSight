using EFT.CameraControl;
using UnityEngine;
using UnityEngine.Rendering;

namespace UstAchae.PVS22
{
    // Live 1x picture (night vision, or thermal for clip-ons with a "clipon_thermal" marker) on the eyepiece for
    // when no optic camera feeds the sight lens: behind a red dot or a holographic sight, or not aiming at all.
    // The prefab's "pvs22_live" disc carries the game's own lens material (CW FX/OpticSight, the one every
    // native scope uses), so it has the native exit-pupil ring and dark idle look. That shader shows the global
    // _CamTex, the optic camera's picture; this disc gets its own instead, per renderer: a private camera at the
    // eye, looking down the clip-on's axis with the field the lens covers from there (so the picture lines up
    // 1x with the world around it), clipped past the clip-on, then turned into the tube picture.
    class LiveLens : MonoBehaviour
    {
        const string LiveNode = "pvs22_live";
        const string FrontMarker = "pvs22_front";
        const string RearMarker = "pvs22_rear";
        const string ThermalMarker = "clipon_thermal";
        const string SightLensNode = "linza";
        const string BackGlassNode = "eyepiece_glass";
        const float MaxEyeDistance = 1.0f;      // the shooter's own clip-on, not ones seen on other weapons
        // How far a scope's OpticSight node may sit off the clip-on's axis and still count as behind it: the node
        // is the scope's "mode" object, often at the mount origin a few cm below the optic axis.
        const float AxisTolerance = 0.10f;
        const float MaxBehind = 0.6f;
        const float DiscRadius = 0.016539544f;  // the lens disc mesh's radius; its node is scaled to the lens
        const float Off = 0.97f;                // _SwitchToSight of a native sight that is not in use
        // The native lens shows _CamTex out to 0.154 of its width from the centre (measured with its own masks):
        // the picture's field is this much wider than the lens's, so the visible part lines up 1x.
        const float Visible = 0.154f;

        static Camera liveCamera;
        static RenderTexture raw, picture;
        static Material process;
        static bool rendering;
        static int renderedFrame = -1;
        static readonly int camTexId = Shader.PropertyToID("_CamTex");
        static readonly int switchId = Shader.PropertyToID("_SwitchToSight");
        static readonly int thermalId = Shader.PropertyToID("_PVS22Thermal");
        static readonly int thermalParamsId = Shader.PropertyToID("_PVS22ThermalParams");
        // Set by EFT's ThermalVision around its camera's render: materials then write their heat into GBuffer0.
        static readonly int thermalOnId = Shader.PropertyToID("_ThermalVisionOn");
        static CommandBuffer copyHeat;

        Renderer disc, sightLens;
        Transform clipOn, front, rear;
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
            // The sight lens and the dark glass behind it sit 2 and 5 mm deeper than this disc, so seen at an
            // angle their rims showed as a crescent around the picture. This disc covers the eyepiece on a
            // weapon (picture or dark lens), so the back glass is never needed here and the sight lens only
            // while an optic camera draws on it.
            lens.sightLens = clipOn.Find(SightLensNode)?.GetComponent<Renderer>();
            Renderer back = clipOn.Find(BackGlassNode)?.GetComponent<Renderer>();
            if (back != null) back.forceRenderingOff = true;
        }

        // Covers the sight lens unless an optic camera is drawing on it, which happens only while aiming through
        // this clip-on itself (a magnified optic behind it draws on its own lens, and the sight lens here would show
        // a stale or see-through picture). LateUpdate order against the optic is not fixed, so allow a frame.
        void LateUpdate()
        {
            if (disc == null) return;
            bool covering = PVS22Plugin.OwnSight != clipOn || Time.frameCount - PVS22Plugin.OwnSightFrame > 1;
            disc.enabled = covering;
            if (sightLens != null) sightLens.forceRenderingOff = covering;
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

            // From the eye down the clip-on's axis (the disc faces +Y toward the shooter), with a field whose visible
            // part is what the lens spans from there, so the picture lines up 1x with the world around the eyepiece
            // when on the axis.
            Vector3 p = eye.transform.position, axis = -transform.up;
            float distance = Vector3.Dot(transform.position - p, axis);
            if (distance < 0.02f) return false;
            float radius = DiscRadius * transform.lossyScale.x;
            liveCamera.CopyFrom(eye);
            liveCamera.targetTexture = raw;
            liveCamera.rect = new Rect(0f, 0f, 1f, 1f);
            liveCamera.transform.SetPositionAndRotation(p, Quaternion.LookRotation(axis, clipOn.up));
            liveCamera.aspect = 1f;
            liveCamera.fieldOfView = 2f * Mathf.Atan(0.5f / Visible * radius / distance) * Mathf.Rad2Deg;
            // Clip past whichever end of the clip-on is farther ahead, like the optic camera path does.
            float clear = Mathf.Max(Vector3.Dot(front.position - p, axis), Vector3.Dot(rear.position - p, axis)) + 0.01f;
            liveCamera.nearClipPlane = Mathf.Max(eye.nearClipPlane, clear);

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
            TubeEffect.SetGlobals(gain, noise, grain * size * 2f * Visible / Mathf.Max(lensPixels, 1f), profile.Phosphor);
            Shader.SetGlobalVector(thermalParamsId, new Vector4(PVS22Plugin.ThermalLevel, PVS22Plugin.ThermalGain, 0f, 0f));
            process.SetFloat(thermalId, thermal ? 1f : 0f);
            Graphics.Blit(raw, picture, process);
            return true;
        }
    }
}
