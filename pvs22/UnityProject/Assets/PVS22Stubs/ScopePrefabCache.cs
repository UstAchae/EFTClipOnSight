using System;
using UnityEngine;

// Serialization stub; matches the game class so the bundle binds to it.
public class ScopePrefabCache : MonoBehaviour
{
    [Serializable]
    public class ScopeModeInfo
    {
        public GameObject ModeGameObject;
        public CollimatorSight CollimatorSight;
        public EFT.CameraControl.OpticSight OpticSight;
        public bool IgnoreOpticsForCameraPlane;
    }

    [Serializable]
    public struct DistaneAngle
    {
        public float Distance;
        public float Angle;
    }

    public bool CanChangeAngleByDistance;
    public Transform WeaponScopeAxis;
    public DistaneAngle[] AngleByRange;
    public ScopeModeInfo[] _scopeModeInfos = new ScopeModeInfo[0];
}
