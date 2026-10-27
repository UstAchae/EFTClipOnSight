using System;
using System.Collections.Generic;
using UnityEngine;

// Serialization stub; matches the game class so the bundle binds to it. The field layout (names, types and
// nested type names) follows the REAP-IR's type tree; finalize_clipons.py fills the values and texture
// references from that scope.
namespace EFT.CameraControl
{
    public class ScopeThermalVisionData : MonoBehaviour
    {
        public bool ThermalVision;
        public bool ThermalVisionIsGlitch;
        public bool ThermalVisionIsPixelated;
        public bool ThermalVisionIsNoisy;
        public bool ThermalVisionIsMotionBlurred;
        public bool ThermalVisionIsFpsStuck;
        public ThermalVisionUtilities ThermalVisionUtilities;
        public StuckFPSUtilities StuckFPSUtilities;
        public MotionBlurUtilities MotionBlurUtilities;
        public GlitchUtilities GlitchUtilities;
        public PixelationUtilities PixelationUtilities;
        public float ChromaticAberrationThermalShift;
        public float UnsharpBias;
        public float UnsharpRadiusBlur;
    }
}

[Serializable] public class ThermalVisionUtilities
{
    public int CurrentRampPalette;
    public float DepthFade;
    public List<RampTexPalletteConnector> RampTexPalletteConnectors;
    public ValuesCoefs ValuesCoefs;
    public Noise NoiseParameters;
    public MaskDescription MaskDescription;
}
[Serializable] public class RampTexPalletteConnector { public int SelectablePalette; public Texture Texture; }
[Serializable] public class ValuesCoefs { public float MainTexColorCoef; public float MinimumTemperatureValue; public float RampShift; }
[Serializable] public class Noise { public Texture NoiseTex; public float NoiseIntensity; }
[Serializable] public class MaskDescription
{
    public Texture Mask;
    public float MaskSize;
    public Texture ThermalMaskTexture;
    public Texture AnvisMaskTexture;
    public Texture BinocularMaskTexture;
    public Texture GasMaskTexture;
    public Texture OldMonocularMaskTexture;
}
[Serializable] public class StuckFPSUtilities { public int MinFramerate; public int MaxFramerate; }
[Serializable] public class MotionBlurUtilities { public Shader Shader; public float BlurAmount; public bool ExtraBlur; }
[Serializable] public class GlitchUtilities
{
    public Shader Shader;
    public Texture2D DisplacementMap;
    public float DigitalMistakeIntensity, DigitalMistakeFrequency, VerticalFlipIntensity, VerticalFlipFrequency;
    public float ColorSwitchIntensity, ColorSwitchFrequency, VerticalJumpCoef, VerticalJumpFrequency, VerticalJumpTimeScale;
    public float ScanLineJitterCoef, ScanLineJitterFrequency, HorizontalShake, HorizontalShakeFrequency;
    public float ColorDriftCoef, ColorDriftFrequency, MaxColorDrift;
}
[Serializable] public class PixelationUtilities { public int Mode; public Shader PixelationShader; public float BlockCount; public float Alpha; public Texture PixelationMask; }
