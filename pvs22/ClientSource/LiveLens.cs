using EFT.CameraControl;
using UnityEngine;
using UnityEngine.Rendering;

namespace UstAchae.PVS22
{
    // Live 1x picture (night vision, or thermal for clip-ons with a "clipon_thermal" marker) on the eyepiece for when no optic camera feeds the sight lens: behind a red dot or a
    // holographic sight, or not aiming at all. Without it the lens keeps showing the last frame an optic
    // camera drew. A private camera copies the player camera, clips everything up to the front of the
    // clip-on (its housing and the sight behind it), and renders into a texture that the prefab's
    // "pvs22_live" disc shows in screen space, so the picture lines up with the world around the eyepiece.
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

        static Camera liveCamera;
        static RenderTexture target;
        static bool rendering;
        static int renderedFrame = -1;
        static readonly int texId = Shader.PropertyToID("_PVS22LiveTex");
        static readonly int onId = Shader.PropertyToID("_PVS22LiveOn");
        static readonly int modeId = Shader.PropertyToID("_PVS22LiveMode");
        static readonly int fovId = Shader.PropertyToID("_PVS22LiveFov");
        static readonly int thermalParamsId = Shader.PropertyToID("_PVS22ThermalParams");
        // Set by EFT's ThermalVision around its camera's render: materials then write their heat into GBuffer0.
        static readonly int thermalOnId = Shader.PropertyToID("_ThermalVisionOn");
        static CommandBuffer copyHeat;

        Renderer disc, sightLens;
        Transform clipOn, front, rear;
        MaterialPropertyBlock block;
        bool thermal;
        float fov;
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
            lens.fov = ImageProfile.For(clipOn).Fov;
            // The sight lens and the dark glass behind it sit 2 and 5 mm deeper than this disc, so seen at an
            // angle their rims showed as a crescent around the picture. This disc covers the eyepiece on a
            // weapon (picture or coated glass), so the back glass is never needed here and the sight lens only
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
            // otherwise, so the extra render (about 5 ms a frame) would be wasted. Other weapons' clip-ons and
            // other cameras show the coated glass.
            if (Time.unscaledTime - checkedAt > 0.5f)
            {
                scopeBehind = ScopeBehind();
                checkedAt = Time.unscaledTime;
            }
            float pupil = !scopeBehind && player && (eye.transform.position - transform.position).sqrMagnitude < MaxEyeDistance * MaxEyeDistance ? 1f : 0f;
            disc.GetPropertyBlock(block);
            block.SetFloat(onId, pupil);
            block.SetFloat(modeId, thermal ? 1f : 0f);
            block.SetFloat(fovId, fov);
            disc.SetPropertyBlock(block);
            // Every other frame (about 30 Hz at 60 fps, close to a tube's own refresh): halves the extra render's cost.
            if (pupil <= 0f || Time.frameCount - renderedFrame < 2) return;

            Render(eye);
            renderedFrame = Time.frameCount;
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

        void Render(Camera eye)
        {
            if (liveCamera == null)
            {
                var go = new GameObject("PVS22 live camera");
                DontDestroyOnLoad(go);
                liveCamera = go.AddComponent<Camera>();
                liveCamera.enabled = false;
            }
            float scale = PVS22Plugin.LiveResolution;
            int w = Mathf.Max(64, (int)(eye.pixelWidth * scale)), h = Mathf.Max(64, (int)(eye.pixelHeight * scale));
            if (target == null || target.width != w || target.height != h)
            {
                if (target != null) target.Release();
                target = new RenderTexture(w, h, 24, RenderTextureFormat.ARGBHalf) { name = "PVS22 live" };
            }

            liveCamera.CopyFrom(eye);
            liveCamera.targetTexture = target;
            liveCamera.rect = new Rect(0f, 0f, 1f, 1f);
            // Clip past whichever end of the clip-on is farther ahead, like the optic camera path does.
            Vector3 p = eye.transform.position, f = eye.transform.forward;
            float clear = Mathf.Max(Vector3.Dot(front.position - p, f), Vector3.Dot(rear.position - p, f)) + 0.01f;
            liveCamera.nearClipPlane = Mathf.Max(eye.nearClipPlane, clear);

            // Thermal: render the scene the way EFT's ThermalVision does (heat flag on, GBuffer0 copied over the
            // lit image before transparents); the eyepiece shader then maps that heat white-hot.
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

            // The same tube model as the optic-camera effect, at 1x (no over-magnification). The grain is in
            // pixels of this lower-resolution picture, so it is scaled to keep the on-screen size.
            ImageProfile profile = ImageProfile.For(clipOn);
            TubeEffect.Settings(profile, 1f, out float gain, out float noise, out float grain);
            TubeEffect.SetGlobals(gain, noise, grain * PVS22Plugin.LiveResolution, profile.Phosphor);
            Shader.SetGlobalTexture(texId, target);
            Shader.SetGlobalVector(thermalParamsId, new Vector4(PVS22Plugin.ThermalLevel, PVS22Plugin.ThermalGain, 0f, 0f));
        }
    }
}
