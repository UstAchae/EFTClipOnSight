using UnityEngine;

namespace UstAchae.PVS22
{
    // How each night-vision clip-on's picture differs from the PVS-22, whose look the config's Brightness, Noise,
    // Tint and Live gain set. From the units' published figures: the PVS-27's F/1.0 catadioptric objective
    // gathers about twice the PVS-22's light and resolves 4.2-5.0 cy/mr against 3.2-3.5 (brighter, cleaner,
    // finer grain); the PVS-30's 120 mm objective is built for 12-20x day scopes (finest grain) and current
    // units mostly carry white-phosphor tubes.
    readonly struct ImageProfile
    {
        public readonly string Name;
        public readonly float Gain, Noise, Grain;  // multipliers; Grain is the noise grain size
        public readonly Color Phosphor;           // screen colour, peak 1: P43 green or P45 white
        // Highest day-scope power the maker rates it for (PVS-22 up to 12x; PVS-27 3-20x; PVS-30 up to 20x;
        // UTC XII 10x). Past it the day scope only enlarges the clip-on's own limits: its resolution, the
        // tube's grain (or the sensor's pixel grid) and, through the shrinking exit pupil, its brightness.
        public readonly float RatedPower;
        // Limiting resolution in cycles per milliradian (PVS-22 3.2-3.5, PVS-27 4.2-5.0; the PVS-30 taken as
        // the PVS-27). The day scope enlarges this fixed blur with its power. 0 for the thermal, whose limit
        // is its pixel grid (shown by pixelation instead).
        public readonly float Resolution;

        ImageProfile(string name, float gain, float noise, float grain, Color phosphor, float ratedPower, float resolution)
        {
            Name = name; Gain = gain; Noise = noise; Grain = grain; Phosphor = phosphor; RatedPower = ratedPower;
            Resolution = resolution;
        }

        // P43 green-yellow phosphor and the bluish-white P45 of white-phosphor tubes.
        static readonly Color P43 = new Color(0.39f, 1.00f, 0.27f), P45 = new Color(0.60f, 0.84f, 0.99f);
        static readonly ImageProfile PVS22 = new ImageProfile("pvs22", 1f, 1f, 1f, P43, 12f, 3.35f);
        static readonly ImageProfile PVS27 = new ImageProfile("pvs27", 1.4f, 0.6f, 0.75f, P43, 20f, 4.6f);
        static readonly ImageProfile PVS30 = new ImageProfile("pvs30", 1.15f, 0.75f, 0.6f, P45, 20f, 4.6f);
        static readonly ImageProfile UTC = new ImageProfile("utc", 1f, 1f, 1f, P45, 10f, 0f);

        // Magnification of the optic camera: native scopes give power x field of view of 23-26.6 degrees (fixed
        // ELCAN 4x at 5.75, PS-320 6x at 4.08; variable March 3-24 at 25, ATACR 7-35 at 26.6, whose FOV follows
        // the zoom). 25 keeps the estimate within about 7% of the dial.
        public static float Magnification(float fieldOfView) => 25f / Mathf.Max(fieldOfView, 0.1f);

        // Day-scope power as a fraction of the rating (1 = at the rating).
        public float RatingFraction(float fieldOfView) => Magnification(fieldOfView) / RatedPower;

        // How far past its rating the day scope magnifies, 1 at or below it.
        public float Overmagnification(float fieldOfView) => Mathf.Max(1f, RatingFraction(fieldOfView));

        // By the clip-on prefab's root name (instances are "(Clone)"s of it).
        public static ImageProfile For(Transform clipOn)
        {
            string name = clipOn != null ? clipOn.name : "";
            if (name.StartsWith("ustachae_pvs27")) return PVS27;
            if (name.StartsWith("ustachae_pvs30")) return PVS30;
            if (name.StartsWith("ustachae_utc")) return UTC;
            return PVS22;
        }
    }
}
