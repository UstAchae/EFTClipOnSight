using System;
using UnityEngine;

// Serialization stub; matches the game class so the bundle binds to it.
namespace EFT.CameraControl
{
    public class ScopeData : MonoBehaviour
    {
        public ScopeReticle Reticle;
        public ScopeNightVisionData NightVisionData;
        public ScopeThermalVisionData ThermalVisionData;
        public ScopeEffectsData PostEffectsData;
    }
}
