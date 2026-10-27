using System;
using UnityEngine;

// Serialization stub; matches the game class so the bundle binds to it.
namespace EFT.CameraControl
{
    public class OpticSight : MonoBehaviour
    {
        public Renderer LensRenderer;
        public Transform ScopeTransform;
        public float DistanceToCamera;
        public ScopeData ScopeData;
        public bool IsThermalSightAvailableAt45Degrees;
    }
}
