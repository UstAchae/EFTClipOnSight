using System.Collections.Generic;
using EFT.CameraControl;
using HarmonyLib;
using UnityEngine;

namespace UstAchae.PVS22
{
    // Slides the clip-on along the rail so its rear end butts against the front of the sight behind it on the
    // same weapon: a magnified optic, a red dot or holographic sight, or, with no sight in them, the rings or
    // riser that would carry one. Runs whenever a mod goes into or out of any slot, so the order in which the
    // weapon is assembled does not matter. With nothing behind it the clip-on stays where the prefab put it.
    static class ClipOnPlacement
    {
        const string FrontMarker = "pvs22_front";
        const string MeshNode = "an_pvs22_LOD0";
        const float Gap = 0.001f;
        // How far the clip-on may slide from its slot: forward slots that only take lasers (an M14 chassis' front
        // rail, a handguard's front top rail) can sit well ahead of the optic, so the backward reach is long.
        const float MinShift = -0.45f, MaxShift = 0.30f;
        // A sight or mount counts when it sits behind the clip-on's slot and this close to its centreline;
        // canted and offset sights are farther out and are left alone.
        const float SideTolerance = 0.035f;

        // In the clip-on's own frame +Z is toward the muzzle. The optical axis height comes from the prefab's
        // "clipon_axis" marker; the PVS-22 predates it and sits at 34.1 mm (prepare_mesh.py).
        const string AxisMarker = "clipon_axis";
        const float PVS22AxisHeight = 0.0341f;

        internal static float AxisHeight(Transform clipOn)
        {
            Transform marker = clipOn.Find(AxisMarker);
            return marker != null ? marker.localPosition.y : PVS22AxisHeight;
        }

        // Baked local positions of the clip-on's children, taken the first time each instance is seen.
        class Rig : MonoBehaviour
        {
            public Transform[] Children;
            public Vector3[] Baked;
            public float NearZ;   // rear end (toward the shooter) with no shift applied
            public float MidZ;    // middle of the body with no shift applied
            int weaponId, partCount, nextCheck;

            // A weapon view is built branch by branch (the clip-on goes into its handguard before the handguard
            // is on the weapon, the scope arrives on another branch), and item views are pooled and reused, so
            // the slot events alone often run before the optic exists or while the clip-on is off any weapon.
            // Re-fit whenever the clip-on is on another weapon or its weapon's part count changes.
            void LateUpdate()
            {
                if (Time.frameCount < nextCheck) return;
                nextCheck = Time.frameCount + 10;
                WeaponPrefab weapon = GetComponentInParent<WeaponPrefab>();
                if (weapon == null)
                {
                    // On its own (inspect view, inventory): back to the prefab's place.
                    if (weaponId != 0 && (transform.parent == null || !transform.parent.name.StartsWith("mod_"))) Shift(this, 0f);
                    weaponId = 0;
                    return;
                }
                int parts = weapon.GetComponentsInChildren<Transform>(true).Length;
                if (weapon.GetInstanceID() == weaponId && parts == partCount) return;
                weaponId = weapon.GetInstanceID();
                partCount = parts;
                Refit(weapon.transform, null);
            }
        }

        public static void Patch(Harmony harmony)
        {
            harmony.Patch(AccessTools.Method(typeof(ContainerCollectionView.SlotView), nameof(ContainerCollectionView.SlotView.InsertItem)),
                postfix: new HarmonyMethod(typeof(ClipOnPlacement), nameof(AfterInsert)));
            harmony.Patch(AccessTools.Method(typeof(ContainerCollectionView.SlotView), nameof(ContainerCollectionView.SlotView.RemoveItem)),
                prefix: new HarmonyMethod(typeof(ClipOnPlacement), nameof(BeforeRemove)));
            // Inventory icons are rendered once from a freshly built weapon, within one call and before any
            // LateUpdate, so fit the clip-ons right before the capture.
            try
            {
                harmony.Patch(AccessTools.Method(typeof(ItemIconCreator).BaseType, "CaptureSpriteOfModel"),
                    prefix: new HarmonyMethod(typeof(ClipOnPlacement), nameof(BeforeIconCapture)));
            }
            catch (System.Exception e)
            {
                PVS22Plugin.Log?.LogWarning("Icon capture hook unavailable, inventory icons keep the clip-on at its slot: " + e.Message);
            }
            // The icon renderer swaps every shader for "<name>_Icon", falling back to the game's p0 icon shader,
            // which draws our lens and eyepiece materials plain white (they set no _MainTex). Our shaders need
            // no scene lighting, so after the swap they are put back from the replacer's own record.
            try
            {
                harmony.Patch(AccessTools.Method(typeof(ShaderReplacer), nameof(ShaderReplacer.Replace)),
                    postfix: new HarmonyMethod(typeof(ClipOnPlacement), nameof(KeepOwnShaders)));
            }
            catch (System.Exception e)
            {
                PVS22Plugin.Log?.LogWarning("Icon shader hook unavailable, clip-on lenses show white in icons: " + e.Message);
            }
        }

        const string OwnShaders = "UstAchae/PVS22/";

        static void KeepOwnShaders(ShaderReplacer __instance)
        {
            foreach (ShaderReplacer.MaterialPath path in __instance._replacedShaders)
            {
                if (path.OriginalShader == null || !path.OriginalShader.name.StartsWith(OwnShaders) || path.Renderer == null) continue;
                Material[] materials = path.Renderer.materials;  // the per-renderer copies the replacer edited
                materials[path.MaterialIndex].shader = path.OriginalShader;
            }
        }

        static void BeforeIconCapture(GameObject model)
        {
            WeaponPrefab weapon = model != null ? model.GetComponentInChildren<WeaponPrefab>(true) : null;
            if (weapon != null) Refit(weapon.transform, null);
        }

        static void AfterInsert(GameObject itemView)
        {
            if (itemView != null) Refit(itemView.transform, null);
        }

        // The removed view is still parented under the weapon at this point, so leave it out explicitly.
        static void BeforeRemove(ContainerCollectionView.SlotView __instance)
        {
            if (__instance.Bone != null && __instance.ItemView != null) Refit(__instance.Bone, __instance.ItemView);
        }

        static void Refit(Transform anywhere, Transform removed)
        {
            WeaponPrefab weapon = anywhere.GetComponentInParent<WeaponPrefab>(true);  // icon models are still inactive
            Transform root = weapon != null ? weapon.transform : anywhere;

            List<Transform> clipOns = null;
            foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
            {
                if (t.name != FrontMarker || t.parent == null) continue;
                if (removed != null && t.IsChildOf(removed)) continue;
                (clipOns ??= new List<Transform>()).Add(t.parent);
            }
            if (clipOns == null) return;

            List<Transform> sights = SightsAndMounts(root, removed);
            foreach (Transform clipOn in clipOns)
            {
                EyepieceImage.Attach(clipOn);
                LensLighting.Attach(clipOn);
                Rig rig = GetRig(clipOn);
                // Not on a weapon yet (a handguard being assembled, a pooled view): leave it where it is; the rig
                // re-fits once the weapon is complete.
                if (rig == null || weapon == null) continue;
                float shift = 0f;
                bool found = FrontOfSightBehind(clipOn, rig, sights, out float sightFront);
                if (found) shift = Mathf.Clamp(sightFront + Gap - rig.NearZ, MinShift, MaxShift);
                Shift(rig, shift);
            }
        }

        static void Shift(Rig rig, float shift)
        {
            for (int i = 0; i < rig.Children.Length; i++)
            {
                if (rig.Children[i] != null) rig.Children[i].localPosition = rig.Baked[i] + new Vector3(0f, 0f, shift);
            }
        }

        static Rig GetRig(Transform clipOn)
        {
            Rig rig = clipOn.GetComponent<Rig>();
            if (rig != null) return rig;
            Transform mesh = clipOn.Find(MeshNode);
            MeshFilter filter = mesh != null ? mesh.GetComponent<MeshFilter>() : null;
            if (filter == null || filter.sharedMesh == null) return null;
            rig = clipOn.gameObject.AddComponent<Rig>();
            rig.Children = new Transform[clipOn.childCount];
            rig.Baked = new Vector3[clipOn.childCount];
            for (int i = 0; i < clipOn.childCount; i++)
            {
                rig.Children[i] = clipOn.GetChild(i);
                rig.Baked[i] = rig.Children[i].localPosition;
            }
            rig.NearZ = mesh.localPosition.z + filter.sharedMesh.bounds.min.z;
            rig.MidZ = mesh.localPosition.z + filter.sharedMesh.bounds.center.z;
            return rig;
        }

        // Mods that are sights or carry one: anything in a scope, mount or sight slot that holds an OpticSight or
        // a CollimatorSight, or has a scope slot of its own (rings, risers). Receiver parts such as dust covers
        // sit in other slots and are not considered.
        static List<Transform> SightsAndMounts(Transform root, Transform removed)
        {
            var found = new List<Transform>();
            foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
            {
                Transform bone = t.parent;
                if (bone == null || t.name.StartsWith("mod_")) continue;
                if (!(bone.name.StartsWith("mod_scope") || bone.name.StartsWith("mod_mount") || bone.name.StartsWith("mod_sight"))) continue;
                if (removed != null && t.IsChildOf(removed)) continue;
                bool sight = t.GetComponent<OpticSight>() != null || t.GetComponentInChildren<CollimatorSight>(true) != null
                    || t.GetComponentInChildren<OpticSight>(true) != null;
                bool mount = false;
                foreach (Transform c in t) if (c.name.StartsWith("mod_scope")) { mount = true; break; }
                if (sight || mount) found.Add(t);
            }
            return found;
        }

        // How far forward the sights and mounts behind the clip-on reach, in the clip-on's frame: the front-most
        // of them, so a scope in rings counts with its objective and bare rings with their own front. "Behind"
        // goes by the body, not the mounting point: a scope hung in rings on the receiver can be mounted ahead of
        // the clip-on's own slot point while nearly all of it is behind (an M14 with a forward chassis rail).
        static bool FrontOfSightBehind(Transform clipOn, Rig rig, List<Transform> sights, out float front)
        {
            front = float.MinValue;
            foreach (Transform sight in sights)
            {
                if (sight.IsChildOf(clipOn) || clipOn.IsChildOf(sight)) continue;
                float side = clipOn.InverseTransformPoint(sight.position).x;
                bool measured = BodyRange(clipOn, sight, out float rear, out float f);
                bool used = Mathf.Abs(side) <= SideTolerance && measured && rear < rig.MidZ;  // on the centreline, and behind
                if (used && f > front) front = f;
            }
            return front > float.MinValue;
        }

        // Rear-most and front-most points of the sight's own meshes, ignoring anything mounted on its slots.
        static bool BodyRange(Transform clipOn, Transform scope, out float rear, out float front)
        {
            rear = float.MaxValue;
            front = float.MinValue;
            foreach (MeshFilter filter in scope.GetComponentsInChildren<MeshFilter>(true))
            {
                if (filter.sharedMesh == null || OnNestedSlot(filter.transform, scope)) continue;
                Bounds b = filter.sharedMesh.bounds;
                for (int i = 0; i < 8; i++)
                {
                    Vector3 corner = b.center + Vector3.Scale(b.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                    float z = clipOn.InverseTransformPoint(filter.transform.TransformPoint(corner)).z;
                    if (z > front) front = z;
                    if (z < rear) rear = z;
                }
            }
            return front > float.MinValue;
        }

        static bool OnNestedSlot(Transform t, Transform scope)
        {
            for (Transform p = t.parent; p != null && p != scope; p = p.parent)
            {
                if (p.name.StartsWith("mod_")) return true;
            }
            return false;
        }
    }
}
