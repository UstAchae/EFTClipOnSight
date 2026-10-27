using EFT.CameraControl;
using UnityEngine;
using UnityEngine.Rendering;

namespace UstAchae.PVS22
{
    // The live picture on the eyepiece of the shooter's own clip-on (night vision, or thermal for clip-ons with a
    // "clipon_thermal" marker), modelled on the device rather than on a game sight (the user's choice). The clip-on
    // is 1x and afocal: the eye's line through any point of its eyepiece sees the scene in that same direction.
    // So the picture is the scene rendered from the eye itself, cropped to the eyepiece's area on screen, with an
    // oblique near plane on the objective's front face: the clip-on, the sight behind it and the shooter's head
    // drop out, while weapon parts ahead of the objective stay in front of it as on the real weapon. It goes
    // through the same tube model as the optic-camera effect (a thermal clip-on's through the game's own thermal
    // vision with the clip-on's data, as on the optic camera in front of a scope), and the lens shader shows it on the eyepiece glass
    // (_PVS22On), dark wherever the eye's line is beyond half the device's field of view from its axis (the field
    // stop): aiming along the axis the whole field shows, a few degrees off it the stop cuts in from one side, and
    // from the hip only the screen's faint glow is left, so nothing is rendered then. Not on the shooter's weapon
    // (loose, in the inspect view, other players' weapons) the eyepiece stays plain glass.
    class EyepieceImage : MonoBehaviour
    {
        const string GlassNode = "eyepiece_glass";
        const string FrontMarker = "pvs22_front";
        const string RearMarker = "pvs22_rear";
        const string ThermalMarker = "clipon_thermal";
        const string BodyNode = "an_pvs22_LOD0";
        const float GlassMeshRadius = 0.016539544f;  // the glass mesh's radius; its node is scaled to the lens
        const float MaxEyeDistance = 1.0f;           // the shooter's own clip-on, not ones seen on other weapons
        // How far a scope's OpticSight node may sit off the clip-on's axis and still count as behind it: the node
        // is the scope's "mode" object, often at the mount origin a few cm below the optic axis.
        const float AxisTolerance = 0.10f;
        const float MaxBehind = 0.6f;
        const float Margin = 0.15f;                  // extra picture around the eyepiece: it is drawn every other frame
        const float NightGlow = 0.02f, ThermalGlow = 0.01f;  // the screen's light scattered out past the field stop

        static Camera liveCamera;
        static Material process;
        static bool rendering;
        static readonly int onId = Shader.PropertyToID("_PVS22On");
        static readonly int pictureId = Shader.PropertyToID("_PVS22Picture");
        static readonly int viewProjectionId = Shader.PropertyToID("_PVS22VP");
        static readonly int axisId = Shader.PropertyToID("_PVS22Axis");
        static readonly int glowId = Shader.PropertyToID("_PVS22Glow");
        // EFT's ThermalVision, done here by hand: its component needs the main camera's effect components.
        // _ThermalVisionOn makes materials write their heat into GBuffer0, which is copied over the lit image
        // before transparents; after them its shader's passes 2 and 0 turn that heat into the picture.
        static readonly int thermalOnId = Shader.PropertyToID("_ThermalVisionOn");
        static readonly int finalId = Shader.PropertyToID("_FinalRT");
        static CommandBuffer copyHeat, thermalPasses;
        static Material thermalMaterial;

        Renderer glass;
        Transform clipOn, front, rear, body;
        Bounds bodyBounds;
        MaterialPropertyBlock block;
        ImageProfile profile;
        bool thermal;
        ScopeThermalVisionData thermalData;
        bool scopeBehind;
        float checkedAt = -10f;
        int renderedFrame = -10;
        Matrix4x4 viewProjection;
        RenderTexture raw, picture;

        public static void Attach(Transform clipOn)
        {
            Transform node = clipOn.Find(GlassNode);
            if (node == null || node.GetComponent<EyepieceImage>() != null) return;
            EyepieceImage image = node.gameObject.AddComponent<EyepieceImage>();
            image.glass = node.GetComponent<Renderer>();
            image.clipOn = clipOn;
            image.front = clipOn.Find(FrontMarker);
            image.rear = clipOn.Find(RearMarker);
            image.block = new MaterialPropertyBlock();
            image.profile = ImageProfile.For(clipOn);
            image.thermal = clipOn.Find(ThermalMarker) != null;
            if (image.thermal) image.thermalData = clipOn.GetComponentInChildren<ScopeThermalVisionData>(true);
            image.body = clipOn.Find(BodyNode);
            Mesh mesh = image.body != null ? image.body.GetComponent<MeshFilter>()?.sharedMesh : null;
            if (mesh != null) image.bodyBounds = mesh.bounds;
        }

        void OnDestroy()
        {
            if (raw != null) { raw.Release(); picture.Release(); }
        }

        void OnWillRenderObject()
        {
            Camera eye = Camera.current;
            if (rendering || eye == null || glass == null || front == null || rear == null) return;
            // The shooter's own clip-on, seen by the main camera, unless a magnified scope sits behind it: that
            // scope's camera shows the picture through it, and the scope hides the eyepiece.
            bool on = eye == Camera.main && (eye.transform.position - transform.position).sqrMagnitude < MaxEyeDistance * MaxEyeDistance;
            if (on && Time.unscaledTime - checkedAt > 0.5f)
            {
                scopeBehind = ScopeBehind();
                checkedAt = Time.unscaledTime;
            }
            on &= !scopeBehind;

            Vector3 axis = -transform.up;  // the glass faces the shooter along local +Y
            float halfField = profile.Fov * 0.5f;
            glass.GetPropertyBlock(block);
            block.SetFloat(onId, on ? 1f : 0f);
            if (on)
            {
                block.SetVector(axisId, new Vector4(axis.x, axis.y, axis.z, halfField));
                Color phosphor = thermal ? Color.white : profile.Phosphor;
                block.SetColor(glowId, phosphor * (thermal ? ThermalGlow : NightGlow));
                // Render only while some of the field can be seen: the eye's line to the eyepiece centre within half
                // the field plus the eyepiece's own size as the eye sees it. Every other frame (about 30 Hz at 60 fps,
                // close to a tube's own refresh), so the picture covers a margin around the eyepiece.
                Vector3 toGlass = transform.position - eye.transform.position;
                float radius = GlassMeshRadius * transform.lossyScale.x;
                float reach = halfField + Mathf.Asin(Mathf.Clamp01(radius / toGlass.magnitude)) * Mathf.Rad2Deg;
                bool visible = Vector3.Dot(toGlass, axis) > 0f && Vector3.Angle(toGlass, axis) < reach;
                if (visible && Time.frameCount - renderedFrame >= 2 && Render(eye, axis, radius)) renderedFrame = Time.frameCount;
                visible &= picture != null && Time.frameCount - renderedFrame < 3;
                // Without a picture the screen's glow still shows: an empty picture leaves only that.
                block.SetTexture(pictureId, visible ? (Texture)picture : Texture2D.blackTexture);
                block.SetMatrix(viewProjectionId, viewProjection);
            }
            glass.SetPropertyBlock(block);
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

        bool Render(Camera eye, Vector3 axis, float radius)
        {
            if (thermal && thermalData == null) return false;
            if (process == null)
            {
                Shader shader = TubeEffect.ShaderOf(clipOn);
                if (shader == null) return false;
                process = new Material(shader) { hideFlags = HideFlags.DontSave };
            }
            if (liveCamera == null)
            {
                var go = new GameObject("PVS22 eyepiece camera");
                DontDestroyOnLoad(go);
                liveCamera = go.AddComponent<Camera>();
                liveCamera.enabled = false;
            }

            // The eyepiece's area on screen, from points around its rim, with a margin.
            Quaternion rotation = Quaternion.LookRotation(axis, clipOn.up);
            Vector2 lo = new Vector2(1f, 1f), hi = new Vector2(0f, 0f);
            for (int i = 0; i < 12; i++)
            {
                float a = i * Mathf.PI / 6f;
                Vector3 v = eye.WorldToViewportPoint(transform.position + rotation * new Vector3(Mathf.Cos(a), Mathf.Sin(a), 0f) * radius);
                if (v.z <= 0f) return false;
                lo = Vector2.Min(lo, v); hi = Vector2.Max(hi, v);
            }
            Vector2 pad = (hi - lo) * Margin;
            lo = Vector2.Max(lo - pad, Vector2.zero); hi = Vector2.Min(hi + pad, Vector2.one);
            Vector2 size = hi - lo;
            if (size.x <= 0f || size.y <= 0f) return false;

            // The picture's pixels match the screen's, in steps of 128 so it is not reallocated every frame.
            int width = Mathf.Clamp(Mathf.CeilToInt(size.x * eye.pixelWidth / 128f) * 128, 128, 2048);
            int height = Mathf.Clamp(Mathf.CeilToInt(size.y * eye.pixelHeight / 128f) * 128, 128, 2048);
            if (raw == null || raw.width != width || raw.height != height)
            {
                if (raw != null) { raw.Release(); picture.Release(); }
                raw = new RenderTexture(width, height, 24, RenderTextureFormat.ARGBHalf) { name = "PVS22 eyepiece" };
                picture = new RenderTexture(width, height, 0, RenderTextureFormat.ARGB32) { name = "PVS22 eyepiece picture" };
            }

            // The eye's own projection cropped to that area: normalised device x and y rescaled so the area fills it.
            Matrix4x4 projection = eye.nonJitteredProjectionMatrix;
            float cx = lo.x + hi.x - 1f, cy = lo.y + hi.y - 1f;
            Matrix4x4 crop = Matrix4x4.identity;
            crop.m00 = 1f / size.x; crop.m03 = -cx / size.x;
            crop.m11 = 1f / size.y; crop.m13 = -cy / size.y;
            projection = crop * projection;

            // Near plane on the objective's front face, facing away from the eye: everything behind it (the clip-on,
            // the sight behind, the head) is cut away.
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
            Vector3 objective = transform.position + axis * (ahead + 0.002f);

            liveCamera.CopyFrom(eye);
            liveCamera.targetTexture = raw;
            liveCamera.rect = new Rect(0f, 0f, 1f, 1f);
            liveCamera.projectionMatrix = projection;
            Vector4 plane = new Vector4(axis.x, axis.y, axis.z, -Vector3.Dot(axis, objective));
            liveCamera.projectionMatrix = liveCamera.CalculateObliqueMatrix(liveCamera.worldToCameraMatrix.inverse.transpose * plane);
            viewProjection = projection * liveCamera.worldToCameraMatrix;

            if (thermal)
            {
                if (thermalMaterial == null) thermalMaterial = new Material(ShadersFinder.Find("Hidden/ThermalVision")) { hideFlags = HideFlags.DontSave };
                SetThermal(thermalMaterial, thermalData);
                if (copyHeat == null)
                {
                    copyHeat = new CommandBuffer { name = "PVS22 copy heat" };
                    copyHeat.Blit(BuiltinRenderTextureType.GBuffer0, BuiltinRenderTextureType.CameraTarget);
                    thermalPasses = new CommandBuffer { name = "PVS22 thermal" };
                    thermalPasses.GetTemporaryRT(finalId, -1, -1);
                    thermalPasses.Blit(BuiltinRenderTextureType.CameraTarget, finalId);
                    thermalPasses.Blit(finalId, BuiltinRenderTextureType.CameraTarget, thermalMaterial, 2);
                    thermalPasses.Blit(BuiltinRenderTextureType.CameraTarget, finalId, thermalMaterial, 0);
                    thermalPasses.Blit(finalId, BuiltinRenderTextureType.CameraTarget);
                    thermalPasses.ReleaseTemporaryRT(finalId);
                }
                liveCamera.AddCommandBuffer(CameraEvent.BeforeForwardAlpha, copyHeat);
                liveCamera.AddCommandBuffer(CameraEvent.AfterForwardAlpha, thermalPasses);
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
                    liveCamera.RemoveCommandBuffer(CameraEvent.AfterForwardAlpha, thermalPasses);
                }
            }
            if (thermal)
            {
                Graphics.Blit(raw, picture);
                return true;
            }

            // The same tube model as the optic-camera effect, at 1x; the picture's pixels match the screen's.
            TubeEffect.Settings(profile, 1f, out float gain, out float noise, out float grain);
            TubeEffect.SetGlobals(gain, noise, grain * width / Mathf.Max(size.x * eye.pixelWidth, 1f), profile.Phosphor);
            Graphics.Blit(raw, picture, process);
            return true;
        }

        // As ThermalVision.SetMaterialProperties, from the clip-on's data (the REAP-IR's, tuned for the UTC XII).
        static void SetThermal(Material material, ScopeThermalVisionData data)
        {
            ThermalVisionUtilities utilities = data.ThermalVisionUtilities;
            Texture ramp = null;
            foreach (RampTexPalletteConnector connector in utilities.RampTexPalletteConnectors)
                if (connector.SelectablePalette == utilities.CurrentRampPalette) { ramp = connector.Texture; break; }
            material.SetTexture("_RampTex", ramp);
            material.SetFloat("_MainTexColorCoef", utilities.ValuesCoefs.MainTexColorCoef);
            material.SetFloat("_MinimumTemperatureValue", utilities.ValuesCoefs.MinimumTemperatureValue);
            material.SetTexture("_Noise", utilities.NoiseParameters.NoiseTex);
            material.SetFloat("_NoiseIntensity", data.ThermalVisionIsNoisy ? utilities.NoiseParameters.NoiseIntensity : 0f);
            material.SetFloat("_DepthFade", utilities.DepthFade);
            material.SetFloat("_RampShift", utilities.ValuesCoefs.RampShift);
            material.SetFloat("_RadiusBlur", data.UnsharpRadiusBlur);
            material.SetFloat("_Bias", data.UnsharpBias);
        }
    }
}
