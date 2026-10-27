using System.Collections.Generic;
using UnityEngine;

namespace UstAchae.PVS22
{
    // The light and surroundings the clip-on's glass (objective and eyepiece, our lens shader) reflects. In a raid the
    // game feeds a forward shader like ours neither lights nor its reflection probe (in the menu's preview scene it
    // does, which is the only place the glass showed any), so they are found here and passed per renderer: the
    // reflection probe holding the clip-on (_PVS22Env; without one the material's own cubemap stays), and the four
    // strongest lights reaching the lens (_PVS22LightDir/_PVS22LightColor): the sun, lamps and flashlights by their
    // own range, cone and fall-off, each only if nothing solid stands between it and the lens, so the sun stays out
    // of a basement.
    class LensLighting : MonoBehaviour
    {
        const string BodyNode = "an_pvs22_LOD0";
        const string GlassNode = "eyepiece_glass";
        const int Count = 4;                 // lights the shader takes
        const int Candidates = 8;            // strongest lights tested for a clear line to the lens
        const float MaxCameraDistance = 30f;
        const float SelectEvery = 0.1f, ListLightsEvery = 2f, ListProbesEvery = 5f;

        static Light[] lights = new Light[0];
        static ReflectionProbe[] probes = new ReflectionProbe[0];
        static float lightsListed = -100f, probesListed = -100f;
        static int solidMask;
        static readonly int envId = Shader.PropertyToID("_PVS22Env");
        static readonly int envHdrId = Shader.PropertyToID("_PVS22Env_HDR");
        static readonly int envOnId = Shader.PropertyToID("_PVS22EnvOn");
        static readonly int lightDirId = Shader.PropertyToID("_PVS22LightDir");
        static readonly int lightColorId = Shader.PropertyToID("_PVS22LightColor");

        Renderer[] renderers;
        MaterialPropertyBlock block;
        readonly Light[] selected = new Light[Count];
        readonly Vector4[] directions = new Vector4[Count], colours = new Vector4[Count];
        readonly List<(Light light, float score)> candidates = new List<(Light, float)>();
        float selectedAt = -100f;

        public static void Attach(Transform clipOn)
        {
            if (clipOn.GetComponent<LensLighting>() != null) return;
            var list = new List<Renderer>();
            foreach (string node in new[] { BodyNode, GlassNode })
            {
                Renderer r = clipOn.Find(node)?.GetComponent<Renderer>();
                if (r != null) list.Add(r);
            }
            if (list.Count == 0) return;
            LensLighting lighting = clipOn.gameObject.AddComponent<LensLighting>();
            lighting.renderers = list.ToArray();
            lighting.block = new MaterialPropertyBlock();
        }

        void LateUpdate()
        {
            Camera camera = Camera.main;
            if (camera == null || (camera.transform.position - transform.position).sqrMagnitude > MaxCameraDistance * MaxCameraDistance) return;
            bool seen = false;
            foreach (Renderer r in renderers) seen |= r != null && r.isVisible;
            if (!seen) return;

            float now = Time.unscaledTime;
            if (now - lightsListed > ListLightsEvery)
            {
                lights = FindObjectsOfType<Light>();
                lightsListed = now;
                if (solidMask == 0)
                {
                    solidMask = LayerMask.GetMask("HighPolyCollider", "LowPolyCollider", "Terrain");
                    if (solidMask == 0) solidMask = Physics.DefaultRaycastLayers;
                }
            }
            if (now - probesListed > ListProbesEvery)
            {
                probes = FindObjectsOfType<ReflectionProbe>();
                probesListed = now;
            }

            Vector3 position = renderers[renderers.Length - 1].bounds.center;
            if (now - selectedAt > SelectEvery)
            {
                Select(position);
                selectedAt = now;
            }
            for (int i = 0; i < Count; i++)
            {
                directions[i] = Vector4.zero; colours[i] = Vector4.zero;
                if (selected[i] != null && Reach(selected[i], position, out Vector3 direction, out Color colour, out _))
                {
                    directions[i] = direction;
                    colours[i] = colour;
                }
            }
            ReflectionProbe probe = ProbeAt(position);

            foreach (Renderer r in renderers)
            {
                if (r == null) continue;
                r.GetPropertyBlock(block);
                block.SetVectorArray(lightDirId, directions);
                block.SetVectorArray(lightColorId, colours);
                block.SetFloat(envOnId, probe != null ? 1f : 0f);
                if (probe != null)
                {
                    block.SetTexture(envId, probe.texture);
                    block.SetVector(envHdrId, probe.textureHDRDecodeValues);
                }
                r.SetPropertyBlock(block);
            }
        }

        // The strongest lights at the lens with a clear line to it.
        void Select(Vector3 position)
        {
            candidates.Clear();
            int layer = renderers[0].gameObject.layer;
            foreach (Light light in lights)
            {
                if (light == null || !light.isActiveAndEnabled || (light.cullingMask & (1 << layer)) == 0) continue;
                if (!Reach(light, position, out _, out _, out float score) || score <= 0f) continue;
                candidates.Add((light, score));
            }
            candidates.Sort((a, b) => b.score.CompareTo(a.score));
            int found = 0;
            for (int i = 0; i < candidates.Count && i < Candidates && found < Count; i++)
            {
                Light light = candidates[i].light;
                Vector3 toLight = light.type == LightType.Directional ? -light.transform.forward * 500f : light.transform.position - position;
                float distance = toLight.magnitude;
                Vector3 direction = toLight / distance;
                if (Physics.Raycast(position + direction * 0.05f, direction, distance - 0.1f, solidMask, QueryTriggerInteraction.Ignore)) continue;
                selected[found++] = light;
            }
            for (int i = found; i < Count; i++) selected[i] = null;
        }

        // The light's direction from the lens and its colour there (range, Unity's point-light fall-off, the spot
        // cone), and how strong that is.
        static bool Reach(Light light, Vector3 position, out Vector3 direction, out Color colour, out float score)
        {
            colour = light.color * light.intensity;
            score = 0f;
            if (light.type == LightType.Directional)
            {
                direction = -light.transform.forward;
            }
            else
            {
                Vector3 toLight = light.transform.position - position;
                float distance = toLight.magnitude, range = Mathf.Max(light.range, 0.01f);
                direction = toLight / Mathf.Max(distance, 1e-4f);
                if (distance >= range) return false;
                float x = distance / range;
                float fade = 1f / (1f + 25f * x * x) * (1f - x * x);
                if (light.type == LightType.Spot)
                {
                    float cos = Vector3.Dot(light.transform.forward, -direction);
                    float outer = Mathf.Cos(light.spotAngle * 0.5f * Mathf.Deg2Rad), inner = Mathf.Cos(light.innerSpotAngle * 0.5f * Mathf.Deg2Rad);
                    fade *= Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(outer, Mathf.Max(inner, outer + 1e-3f), cos));
                }
                else if (light.type != LightType.Point) return false;
                colour *= fade;
            }
            score = colour.r * 0.3f + colour.g * 0.59f + colour.b * 0.11f;
            return true;
        }

        // The reflection probe holding the lens: the most important, then the smallest.
        static ReflectionProbe ProbeAt(Vector3 position)
        {
            ReflectionProbe best = null;
            float bestVolume = float.MaxValue;
            foreach (ReflectionProbe probe in probes)
            {
                if (probe == null || !probe.isActiveAndEnabled || probe.texture == null || !probe.bounds.Contains(position)) continue;
                Vector3 size = probe.bounds.size;
                float volume = size.x * size.y * size.z;
                if (best == null || probe.importance > best.importance || (probe.importance == best.importance && volume < bestVolume))
                {
                    best = probe;
                    bestVolume = volume;
                }
            }
            return best;
        }
    }
}
