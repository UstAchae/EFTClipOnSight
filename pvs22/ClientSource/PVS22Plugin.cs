using BepInEx;
using BepInEx.Configuration;
using BSG.CameraEffects;
using EFT.CameraControl;
using HarmonyLib;
using UnityEngine;

namespace UstAchae.PVS22
{
    // Clip-on sights (AN/PVS-22, PVS-27, PVS-30, UTC XII): when a clip-on sits in line in front of the optic
    // being looked through, the optic camera renders night vision (or thermal, for clip-ons with a
    // "clipon_thermal" marker), and its near plane moves past the clip-on so the housing itself does not fill
    // the scope picture.
    [BepInPlugin("com.ustachae.pvs22", "Justachae's Clip-on Sight", "0.1.0")]
    public class PVS22Plugin : BaseUnityPlugin
    {
        const string FrontMarker = "pvs22_front";
        const string RearMarker = "pvs22_rear";
        const string ThermalMarker = "clipon_thermal";
        // The rear boot slips over the objective bell, so it may start slightly behind the optic camera.
        const float RearBehindTolerance = 0.06f;
        // How far the clip-on axis may sit off the optic axis and still count as in line.
        const float AxisTolerance = 0.045f;

        static ConfigEntry<float> gain;
        static ConfigEntry<float> noise;
        static ConfigEntry<float> liveResolution;
        static ConfigEntry<float> thermalLevel;
        static ConfigEntry<float> thermalGain;

        // Read by LiveLens, which draws the eyepiece when no optic camera does.
        internal static float Gain => gain.Value;
        internal static float Noise => noise.Value;
        internal static float LiveResolution => liveResolution.Value;
        internal static float ThermalLevel => thermalLevel.Value;
        internal static float ThermalGain => thermalGain.Value;

        static readonly AccessTools.FieldRef<OpticComponentUpdater, OpticSight> sightRef = AccessTools.FieldRefAccess<OpticComponentUpdater, OpticSight>("_opticSight");
        static readonly AccessTools.FieldRef<OpticComponentUpdater, Camera> cameraRef = AccessTools.FieldRefAccess<OpticComponentUpdater, Camera>("opticCamera");
        static readonly AccessTools.FieldRef<OpticComponentUpdater, NightVision> nightVisionRef = AccessTools.FieldRefAccess<OpticComponentUpdater, NightVision>("nightVision");
        static readonly AccessTools.FieldRef<OpticComponentUpdater, ThermalVision> thermalVisionRef = AccessTools.FieldRefAccess<OpticComponentUpdater, ThermalVision>("thermalVision");
        static readonly AccessTools.FieldRef<OpticComponentUpdater, int> cachedOpticRef = AccessTools.FieldRefAccess<OpticComponentUpdater, int>("cachedOpticId");

        static OpticComponentUpdater applied;
        static bool appliedThermal;
        // The optic the settings were applied for. When the optic behind the clip-on is swapped (or removed and
        // mounted again) the game rebuilds the optic camera for it and turns our thermal off, so apply again.
        static OpticSight appliedSight;
        static OpticSight searchedSight;
        static float searchedAt;
        static Transform front, rear;
        static ScopeThermalVisionData clipOnThermal;  // the found clip-on's thermal data, null for night vision

        internal static BepInEx.Logging.ManualLogSource Log;

        void Awake()
        {
            Log = Logger;
            // New section and keys: the old "PVS-22" values were for the game's own night-vision effect.
            gain = Config.Bind("Night vision", "Gain", 30f, new ConfigDescription("Image tube gain of the night-vision clip-ons (the PVS-22; the PVS-27 and PVS-30 are brighter by design).", new AcceptableValueRange<float>(1f, 200f)));
            noise = Config.Bind("Night vision", "Noise", 1f, new ConfigDescription("Scale of the tube noise: grain, scintillation and fixed pattern. 0 turns it off.", new AcceptableValueRange<float>(0f, 3f)));
            thermalLevel = Config.Bind("Thermal", "Live cold level", 0.2f, new ConfigDescription("Heat level shown as black in the thermal eyepiece picture behind a red dot or holographic sight.", new AcceptableValueRange<float>(0f, 1f)));
            thermalGain = Config.Bind("Thermal", "Live gain", 2.5f, new ConfigDescription("Contrast of that thermal picture.", new AcceptableValueRange<float>(0.5f, 10f)));
            liveResolution = Config.Bind("PVS-22", "Live resolution", 0.5f, new ConfigDescription("Resolution of the live eyepiece picture (behind a red dot or holographic sight, or with no sight behind the clip-on): 0.5 renders 1024 x 1024 pixels (the lens shows the middle third), 1 renders 2048 x 2048. It costs one extra scene render every other frame.", new AcceptableValueRange<float>(0.25f, 1f)));
            var harmony = new Harmony("com.ustachae.pvs22");
            harmony.Patch(AccessTools.Method(typeof(OpticComponentUpdater), "LateUpdate"),
                postfix: new HarmonyMethod(typeof(PVS22Plugin), nameof(AfterOpticLateUpdate)));
            ClipOnPlacement.Patch(harmony);
        }

        static void AfterOpticLateUpdate(OpticComponentUpdater __instance)
        {
            OpticSight sight = sightRef(__instance);
            Camera camera = cameraRef(__instance);
            if (sight == null || camera == null) return;

            Transform cam = camera.transform;
            // Looking straight through the PVS-22 itself: it is a 1x night sight, so only the switch matters.
            if (sight.transform.Find(FrontMarker) != null)
            {
                if (sight.transform.Find(ThermalMarker) != null)
                {
                    thermalVisionRef(__instance).On = true;
                    TubeEffect.Hide(camera);
                    MagnificationBlur.Set(camera, null, 0f);
                    return;
                }
                // A clip-on works whenever it is mounted (no on/off switch, user's choice). Our tube picture
                // replaces the game's night vision.
                NightVision own = nightVisionRef(__instance);
                own.enabled = false;
                own.On = false;
                TubeEffect.Show(camera, sight.transform, ImageProfile.For(sight.transform), 1f);
                MagnificationBlur.Set(camera, null, 0f);
                return;
            }
            bool active = FindClipOn(sight) && InLine(cam);
            if (active)
            {
                if (sight != appliedSight) { applied = null; appliedSight = sight; }
                NightVision nightVision = nightVisionRef(__instance);
                ImageProfile profile = ImageProfile.For(front.parent);
                float over = profile.Overmagnification(camera.fieldOfView);
                if (clipOnThermal != null)
                {
                    TubeEffect.Hide(camera);
                    ApplyThermal(__instance, thermalVisionRef(__instance), nightVision, over);
                }
                else
                {
                    nightVision.enabled = false;
                    nightVision.On = false;
                    TubeEffect.Show(camera, front.parent, profile, over);
                    applied = __instance;  // so the optic's own settings come back when the clip-on is gone
                    appliedThermal = false;
                }
                MagnificationBlur.Set(camera, front.parent, MagnificationBlur.RadiusFor(profile, profile.RatingFraction(camera.fieldOfView)));
                // Clip past whichever end of the clip-on is farther down the optic axis.
                float clear = Mathf.Max(Vector3.Dot(front.position - cam.position, cam.forward),
                    Vector3.Dot(rear.position - cam.position, cam.forward)) + 0.01f;
                camera.nearClipPlane = Mathf.Max(sight.CameraData.NearClipPlane, clear);
            }
            else if (applied == __instance)
            {
                // Let the game rebuild the optic's own settings (its own night vision, near plane, effects).
                MagnificationBlur.Set(camera, null, 0f);
                TubeEffect.Hide(camera);
                applied = null;
                cachedOpticRef(__instance) = 0;
                __instance.CopyComponentFromOptic(sight);
            }
        }

        // Thermal clip-on in front of a magnified optic: the optic camera's own ThermalVision, set up from the
        // clip-on's thermal data the same way OpticComponentUpdater.CopyComponentFromOptic does for thermal scopes.
        static void ApplyThermal(OpticComponentUpdater updater, ThermalVision thermalVision, NightVision nightVision, float over = 1f)
        {
            // Every frame, like the night-vision path: the game may switch these back for the optic's own settings.
            nightVision.enabled = false;
            nightVision.On = false;
            thermalVision.enabled = true;
            thermalVision.On = true;
            Overmagnify(thermalVision, over);
            if (applied == updater && appliedThermal) return;
            ScopeThermalVisionData data = clipOnThermal;
            thermalVision.IsGlitch = data.ThermalVisionIsGlitch;
            thermalVision.IsPixelated = data.ThermalVisionIsPixelated;
            thermalVision.IsNoisy = data.ThermalVisionIsNoisy;
            thermalVision.IsMotionBlurred = data.ThermalVisionIsMotionBlurred;
            thermalVision.IsFpsStuck = data.ThermalVisionIsFpsStuck;
            thermalVision.ThermalVisionUtilities = data.ThermalVisionUtilities;
            thermalVision.StuckFpsUtilities = data.StuckFPSUtilities;
            thermalVision.MotionBlurUtilities = data.MotionBlurUtilities;
            thermalVision.GlitchUtilities = data.GlitchUtilities;
            thermalVision.PixelationUtilities = data.PixelationUtilities;
            thermalVision.ChromaticAberrationThermalShift = data.ChromaticAberrationThermalShift;
            thermalVision.UnsharpBias = data.UnsharpBias;
            thermalVision.UnsharpRadiusBlur = data.UnsharpRadiusBlur;
            applied = updater;
            appliedThermal = true;
            thermalOver = -1f;
            Overmagnify(thermalVision, over);
        }

        // Thermal past its rating: the 640x480 sensor's pixel grid shows (pixelation blocks grow with the extra
        // magnification and blend in) and the noise rises. Works on copies, so the clip-on's data stays intact.
        static float thermalOver = -1f;
        static readonly System.Func<object, object> clone = o => AccessTools.Method(typeof(object), "MemberwiseClone").Invoke(o, null);

        static void Overmagnify(ThermalVision thermalVision, float over)
        {
            over = Mathf.Round(over * 20f) / 20f;
            ScopeThermalVisionData data = clipOnThermal;
            if (data == null || over == thermalOver) return;
            thermalOver = over;
            var pixels = (PixelationUtilities)clone(data.PixelationUtilities);
            pixels.BlockCount = data.PixelationUtilities.BlockCount / over;
            pixels.Alpha = Mathf.Clamp01(data.PixelationUtilities.Alpha + (over - 1f) * 1.5f);
            thermalVision.PixelationUtilities = pixels;
            thermalVision.IsPixelated = data.ThermalVisionIsPixelated || over > 1f;
            var utilities = (ThermalVisionUtilities)clone(data.ThermalVisionUtilities);
            utilities.NoiseParameters = (Noise)clone(data.ThermalVisionUtilities.NoiseParameters);
            utilities.NoiseParameters.NoiseIntensity = data.ThermalVisionUtilities.NoiseParameters.NoiseIntensity * Mathf.Pow(over, 1.2f);
            thermalVision.ThermalVisionUtilities = utilities;
        }


        // The clip-on rides on the same weapon as the optic; look for its markers there.
        static bool FindClipOn(OpticSight sight)
        {
            if (sight != searchedSight || Time.unscaledTime - searchedAt > 0.5f)
            {
                searchedSight = sight;
                searchedAt = Time.unscaledTime;
                front = rear = null;
                clipOnThermal = null;
                Transform root = sight.GetComponentInParent<WeaponPrefab>()?.transform ?? sight.transform.root;
                foreach (Transform t in root.GetComponentsInChildren<Transform>())
                {
                    if (t.name != FrontMarker) continue;
                    Transform r = t.parent.Find(RearMarker);
                    if (r == null) continue;
                    front = t;
                    rear = r;
                    if (t.parent.Find(ThermalMarker) != null)
                        clipOnThermal = t.parent.GetComponentInChildren<ScopeThermalVisionData>(true);
                    break;
                }
            }
            return front != null && front.gameObject.activeInHierarchy;
        }

        static bool InLine(Transform cam)
        {
            Vector3 toFront = front.position - cam.position, toRear = rear.position - cam.position;
            float a = Vector3.Dot(toFront, cam.forward), b = Vector3.Dot(toRear, cam.forward);
            // The near end may overlap the objective bell a little; the far end must be ahead of the optic.
            if (Mathf.Min(a, b) < -RearBehindTolerance || Mathf.Max(a, b) <= 0f) return false;
            return Vector3.ProjectOnPlane(toFront, cam.forward).magnitude < AxisTolerance
                && Vector3.ProjectOnPlane(toRear, cam.forward).magnitude < AxisTolerance;
        }
    }
}
