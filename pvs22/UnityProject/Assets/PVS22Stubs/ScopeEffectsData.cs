using System;
using UnityEngine;

// Serialization stub; matches the game class so the bundle binds to it.
namespace EFT.CameraControl
{
    public class ScopeEffectsData : MonoBehaviour
    {
        public bool ChromaticAberration;
        public int ChromaticAberrationAniso;
        public float ChromaticAberrationShift;
        public bool BloomOptimized;
        public float BloomOptimizedIntensity;
        public float BloomOptimizedThreshold;
        public float BloomOptimizedBlurSize;
        public bool FastVignette;
        public bool UltimateBloom;
        public bool Fisheye;
        public bool Tonemapping;
        public float White;
        public float AdaptionSpeed;
        public float ExposureAdjustment;
        public float MiddleGrey;
        public int AdaptiveTextureSize;
        public int Type;
    }
}
