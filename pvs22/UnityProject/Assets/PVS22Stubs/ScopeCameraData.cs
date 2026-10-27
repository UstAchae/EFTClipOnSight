using System;
using UnityEngine;

// Serialization stub; matches the game class so the bundle binds to it.
namespace EFT.CameraControl
{
    public class ScopeCameraData : MonoBehaviour
    {
        public float FieldOfView;
        public float NearClipPlane;
        public float FarClipPlane;
        public bool OpticCullingMask;
        public float OpticCullingMaskScale;
        public bool CameraLodBiasController;
        public float LodBiasFactor;
    }
}
