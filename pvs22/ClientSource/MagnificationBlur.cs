using UnityEngine;

namespace UstAchae.PVS22
{
    // Softens the optic camera's picture by the clip-on's own limited resolution, which the day scope enlarges
    // with its power. The radius grows from zero
    // (UstAchae/PVS22/Blur, carried in the bundle on the hidden "pvs22_blur" renderer), two turned passes, at
    // half or quarter resolution once it is wide. Runs after the tube or thermal effect.
    class MagnificationBlur : MonoBehaviour
    {
        const string CarrierNode = "pvs22_blur";
        static readonly int blurId = Shader.PropertyToID("_PVS22Blur");

        Material material;
        float radius;  // pixels at 1080 lines

        // The clip-on's own blur, half a cycle of its limiting resolution, as the day scope enlarges it: in
        // proportion to the power. The optic picture spans 25 degrees / power vertically, 2.48 px per mrad at
        // 1x on 1080 lines, so the radius is 2.48 x 0.5 / resolution x power (PVS-22 about 4.5 px at 12x).
        public static float RadiusFor(ImageProfile profile, float fraction)
        {
            if (profile.Resolution <= 0f) return 0f;
            float power = fraction * profile.RatedPower;
            return Mathf.Min(1.24f / profile.Resolution * power, 60f);
        }

        public static void Set(Camera camera, Transform clipOn, float radius)
        {
            var blur = camera.GetComponent<MagnificationBlur>();
            if (radius <= 0.05f)
            {
                if (blur != null && blur.enabled) blur.enabled = false;
                return;
            }
            if (blur == null)
            {
                Transform node = clipOn != null ? clipOn.Find(CarrierNode) : null;
                Renderer carrier = node != null ? node.GetComponent<Renderer>() : null;
                if (carrier == null || carrier.sharedMaterial == null) return;
                blur = camera.gameObject.AddComponent<MagnificationBlur>();
                blur.material = new Material(carrier.sharedMaterial.shader) { hideFlags = HideFlags.DontSave };
            }
            blur.radius = radius;
            if (!blur.enabled) blur.enabled = true;
        }

        public static void Remove(Camera camera)
        {
            var blur = camera != null ? camera.GetComponent<MagnificationBlur>() : null;
            if (blur != null) Destroy(blur);
        }

        void OnRenderImage(RenderTexture source, RenderTexture destination)
        {
            float px = radius * source.height / 1080f;
            int scale = px > 16f ? 4 : px > 6f ? 2 : 1;
            px /= scale;
            var a = RenderTexture.GetTemporary(source.width / scale, source.height / scale, 0, source.format);
            var b = RenderTexture.GetTemporary(a.width, a.height, 0, source.format);
            a.filterMode = b.filterMode = FilterMode.Bilinear;
            Graphics.Blit(source, a);
            material.SetVector(blurId, new Vector4(px, 0f, 0f, 0f));
            Graphics.Blit(a, b, material);
            material.SetVector(blurId, new Vector4(px * 0.6f, 0.39f, 0f, 0f));
            Graphics.Blit(b, destination, material);
            RenderTexture.ReleaseTemporary(a);
            RenderTexture.ReleaseTemporary(b);
        }

        void OnDestroy()
        {
            if (material != null) Destroy(material);
        }
    }
}
