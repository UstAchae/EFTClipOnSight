using System;
using UnityEngine;
public class PreviewPivot : MonoBehaviour
{
    public Vector3 pivotPosition;
    public Quaternion pivotRotation;
    public Vector3 scale;
    public Vector3 SpawnPosition;
    public IconSettings Icon;
    [Serializable]
    public class IconSettings
    {
        public Vector3 position;
        public byte hasOffset;
        public Quaternion rotation;
        public float boundsScale;
        public float perspective;
        public byte orthographic;
        public float orthographicSize;
    }
}
