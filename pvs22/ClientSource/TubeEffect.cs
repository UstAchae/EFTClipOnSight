using UnityEngine;

namespace UstAchae.PVS22
{
    // The clip-ons' image-intensifier picture on an optic camera, replacing the game's night vision when a
    // night-vision clip-on sits in front of the scope or is itself the sight. The shader (UstAchae/PVS22/Tube,
    // model in PVS22Tube.cginc) ships in each clip-on bundle on the hidden "pvs22_tube" renderer.
    class TubeEffect : MonoBehaviour
    {
        const string CarrierNode = "pvs22_tube";
        static readonly int paramsId = Shader.PropertyToID("_PVS22TubeParams");
        static readonly int tintId = Shader.PropertyToID("_PVS22TubeTint");
        static readonly int spectralId = Shader.PropertyToID("_PVS22TubeSpectral");
        // Gen 3 photocathodes respond mostly to red and near infrared, which the scene's red and green stand in for.
        static readonly Vector4 Spectral = new Vector4(0.45f, 0.45f, 0.10f, 0f);

        Material material;
        float gain, noise, grain;
        Color phosphor;

        // Turns the effect on for this camera with the clip-on's picture; clipOn supplies the shader.
        public static void Show(Camera camera, Transform clipOn, ImageProfile profile, float over)
        {
            var effect = camera.GetComponent<TubeEffect>();
            if (effect == null)
            {
                Shader shader = ShaderOf(clipOn);
                if (shader == null) return;
                // Image effects run in component order and the magnification blur must come after the tube.
                MagnificationBlur.Remove(camera);
                effect = camera.gameObject.AddComponent<TubeEffect>();
                effect.material = new Material(shader) { hideFlags = HideFlags.DontSave };
            }
            Settings(profile, over, out effect.gain, out effect.noise, out effect.grain);
            effect.phosphor = profile.Phosphor;
            if (!effect.enabled) effect.enabled = true;
        }

        public static void Hide(Camera camera)
        {
            var effect = camera != null ? camera.GetComponent<TubeEffect>() : null;
            if (effect != null && effect.enabled) effect.enabled = false;
        }

        // The tube's gain, noise scale and grain for a clip-on, dimmer and noisier past its rated day-scope power.
        public static void Settings(ImageProfile profile, float over, out float gain, out float noise, out float grain)
        {
            gain = PVS22Plugin.Gain * profile.Gain / Mathf.Pow(over, 0.7f);
            noise = PVS22Plugin.Noise * profile.Noise * Mathf.Pow(over, 1.2f);
            grain = 1.5f * profile.Grain;
        }

        public static void SetGlobals(float gain, float noise, float grain, Color phosphor)
        {
            Shader.SetGlobalVector(paramsId, new Vector4(gain, noise, grain, Time.time));
            Shader.SetGlobalVector(tintId, phosphor);
            Shader.SetGlobalVector(spectralId, Spectral);
        }

        internal static Shader ShaderOf(Transform clipOn)
        {
            Transform node = clipOn != null ? clipOn.Find(CarrierNode) : null;
            Renderer carrier = node != null ? node.GetComponent<Renderer>() : null;
            return carrier != null && carrier.sharedMaterial != null ? carrier.sharedMaterial.shader : null;
        }

        void OnRenderImage(RenderTexture source, RenderTexture destination)
        {
            SetGlobals(gain, noise, grain, phosphor);
            Graphics.Blit(source, destination, material);
        }

        void OnDestroy()
        {
            if (material != null) Destroy(material);
        }
    }
}
