using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using SPTarkov.Common.Models.Logging;
using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.DI;
using SPTarkov.Server.Core.Helpers.Server;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.Common.Tables;
using SPTarkov.Server.Core.Models.Spt.Mod;
using SPTarkov.Server.Core.Models.Spt.Tables;
using SPTarkov.Server.Core.Services.Modding.Custom;
using SPTarkov.Server.Core.Utils;
using SPTarkov.Server.Core.Utils.Json;

namespace UstAchaePVS22;

public record ModMetadata : IModMetadata
{
    public string ModGuid { get; init; } = "com.ustachae.pvs22";
    public string Name { get; init; } = "Justachae's Clip-on Sight";
    public string Author { get; init; } = "UstAchae";
    public List<string>? Contributors { get; init; }
    public SemanticVersioning.Version Version { get; init; } = new("0.1.0");
    public SemanticVersioning.Range SptVersion { get; init; } = new("~4.1.6");
    public bool HasPrepatcher { get; init; }
    public List<string>? Incompatibilities { get; init; }
    public Dictionary<string, SemanticVersioning.Range>? ModDependencies { get; init; }
    public string? Url { get; init; }
    public string License { get; init; } = "All rights reserved";
}

// Runs after the database and other content mods, so modded handguards and receivers get the clip-on too.
[Injectable(InjectionType.Transient, TypePriority = OnLoadOrder.Preload + 50000)]
public class PVS22Mod(
    ISptLogger<PVS22Mod> logger, ModHelper modHelper, CustomItemService customItemService,
    TemplateTable templateTable, TradersTable tradersTable
) : IOnLoad
{
    const string Mount = "55818b224bdc2dde698b456f";
    const string Receiver = "55818a304bdc2db5418b457d";
    const string GasBlock = "56ea9461d2720b67698b456f";
    const string Stock = "55818a594bdc2db9688b456a";
    const string TacticalCombo = "55818b164bdc2ddc698b456c";
    // Optic categories: OpticScope, AssaultScope, SpecialScope, Collimator, CompactCollimator.
    static readonly string[] Optics = ["55818ae44bdc2dde698b456c", "55818add4bdc2d5b648b456f", "55818aeb4bdc2ddc698b456a",
        "55818ad54bdc2ddc698b4569", "55818acf4bdc2dde698b456b"];
    const string Handguard = "55818a104bdc2db9688b4569";
    const string MPR45 = "5649a2464bdc2d91118b45a8";  // NcStar MPR45 backup rail
    static readonly string[] RailSlots = ["mod_scope", "mod_mount", "mod_tactical", "mod_sight"];  // as in top_rails.py

    public Task OnLoadAsync(CancellationToken cancellationToken)
    {
        string modPath = modHelper.GetAbsolutePathToModFolder(Assembly.GetExecutingAssembly());
        var options = JsonUtil.JsonSerializerOptionsNoIndent ?? new JsonSerializerOptions();
        var topRails = JsonSerializer.Deserialize<Dictionary<string, Dictionary<string, bool>>>(
            File.ReadAllText(System.IO.Path.Combine(modPath, "db", "top_rails.json")), options) ?? [];
        // The PVS-22, then every clip-on the clipons pipeline added (db/items/*.json), all built the same way.
        string itemsDir = System.IO.Path.Combine(modPath, "db", "items");
        var catalogs = new List<string> { System.IO.Path.Combine(modPath, "db", "pvs22.json") };
        if (Directory.Exists(itemsDir)) catalogs.AddRange(Directory.GetFiles(itemsDir, "*.json").OrderBy(f => f));
        var clipOns = new List<MongoId>();
        foreach (string file in catalogs) if (LoadItem(file, options, topRails) is MongoId id) clipOns.Add(id);
        AddConflicts(clipOns);
        return Task.CompletedTask;
    }

    MongoId? LoadItem(string file, JsonSerializerOptions options, Dictionary<string, Dictionary<string, bool>> topRails)
    {
        var catalog = JsonNode.Parse(File.ReadAllText(file))!.AsObject();
        var template = JsonSerializer.Deserialize<TemplateItem>(catalog["item"], options)
            ?? throw new InvalidOperationException(file + ": template did not deserialize");

        var locales = new Dictionary<string, LocaleDetails>();
        foreach (var pair in catalog["locales"]!.AsObject())
        {
            locales[pair.Key] = new LocaleDetails
            {
                Name = pair.Value!["name"]!.GetValue<string>(),
                ShortName = pair.Value!["shortName"]!.GetValue<string>(),
                Description = pair.Value!["description"]!.GetValue<string>()
            };
        }
        string name = locales.TryGetValue("en", out var en) ? en.ShortName! : template.Id.ToString();

        // Only the AN/PVS-30's bundle ships with the mod; the others are built by build_models.py from the
        // player's own purchased models. An item without its bundle stays out of the game.
        string bundle = template.Properties?.Prefab?.Path ?? "";
        if (!File.Exists(System.IO.Path.Combine(modHelper.GetAbsolutePathToModFolder(Assembly.GetExecutingAssembly()), "bundles", bundle)))
        {
            logger.Info($"{name} not enabled: its model is not built (see build_models.py in the mod folder)");
            return null;
        }

        double price = catalog["price"]!.GetValue<double>();
        var result = customItemService.CreateItem(new NewItemDetails
        {
            NewItem = template,
            AddToHandbook = true,
            HandbookParentId = catalog["handbookParentId"]!.GetValue<string>(),
            HandbookPriceRoubles = price,
            FleaPriceRoubles = price,
            AddToFleaPriceDb = true,
            Locales = locales
        }, Assembly.GetExecutingAssembly());
        if (!result.Success)
        {
            logger.Error($"{name} item was not created: " + string.Join("; ", result.Errors ?? []));
            return null;
        }

        int slots = AddToTopRails(template.Id, topRails);
        AddListing(template.Id, catalog["listing"]!.AsObject(), name);
        logger.Success($"{name} loaded, fits {slots} rail slots");
        return template.Id;
    }

    // Angled offset mounts that carry a sight, such as the NcStar MPR45 between the scope and the clip-on, would
    // sit in the clip-on's line of sight (the user's rule; front sights stay allowed). Either way round, the
    // one is not allowed while the other is on the weapon.
    void AddConflicts(List<MongoId> clipOns)
    {
        var blocked = new HashSet<MongoId>();
        var angled = new System.Text.RegularExpressions.Regex(@"mpr45|offset|canted|45_?deg", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        foreach (var item in templateTable.Items.Values)
            if (IsA(item.Id, Mount) && item.Name != null && angled.IsMatch(item.Name)
                && item.Properties?.Slots?.Any(s => Takes(s, t => Optics.Any(o => IsA(t, o)))) == true)
                blocked.Add(item.Id);
        blocked.ExceptWith(clipOns);
        foreach (var id in blocked)
        {
            if (!templateTable.Items.TryGetValue(id, out var item) || item.Properties is null) continue;
            item.Properties.ConflictingItems ??= [];
            foreach (var c in clipOns) item.Properties.ConflictingItems.Add(c);
            foreach (var c in clipOns)
            {
                var own = templateTable.Items[c].Properties!;
                own.ConflictingItems ??= [];
                own.ConflictingItems.Add(id);
            }
        }
    }

    bool IsA(MongoId id, string ancestor)
    {
        for (int guard = 0; guard < 16 && templateTable.Items.TryGetValue(id, out var t); guard++)
        {
            if (t.Id == ancestor) return true;
            id = t.Parent;
        }
        return false;
    }

    // A clip-on goes where a laser device can sit straight on top (the user's rule): a slot that takes a
    // TacticalCombo device and sits on top, on a handguard, rail mount, receiver, gas block or stock, but
    // not on a mount that carries an optic (scope bases and rings; the clip-on belongs in front of those).
    // Which slots sit on top comes from top_rails.json, which top_rails.py measures from the slot node
    // positions in every vanilla prefab; slots it doesn't know (modded items, slots other mods add) count as
    // on top when they are a mod_scope or take the NcStar MPR45 backup rail. What a slot accepts is checked
    // here, after other mods have added their entries.
    int AddToTopRails(MongoId pvs, Dictionary<string, Dictionary<string, bool>> topRails)
    {
        string[] owners = [Handguard, Mount, Receiver, GasBlock, Stock];
        // Decided once, before any clip-on is added: the clip-ons are special scopes themselves, so afterwards
        // every rail mount would look like an optic mount.
        opticMounts ??= templateTable.Items.Values.Where(m => IsA(m.Id, Mount)
            && m.Properties?.Slots?.Any(s => Takes(s, t => Optics.Any(o => IsA(t, o)))) == true).Select(m => m.Id).ToHashSet();
        sideMounts ??= SideMounts(topRails);
        int added = 0;
        foreach (var owner in templateTable.Items.Values)
        {
            if (owner.Id == pvs || owner.Properties?.Slots is null || !owners.Any(o => IsA(owner.Id, o))) continue;
            if (opticMounts.Contains(owner.Id) || sideMounts.Contains(owner.Id)) continue;
            topRails.TryGetValue(owner.Id.ToString(), out var measured);
            foreach (var slot in owner.Properties.Slots)
            {
                var filter = slot.Properties?.Filters?.FirstOrDefault()?.Filter;
                if (slot.Name is null || filter is null || filter.Contains(pvs)) continue;
                bool onTop = measured != null && measured.TryGetValue(slot.Name, out bool top) ? top
                    : slot.Name.StartsWith("mod_scope") || filter.Contains(MPR45);
                if (!onTop || !Takes(slot, t => templateTable.Items.TryGetValue(t, out var item) && item.Parent == TacticalCombo)) continue;
                filter.Add(pvs);
                added++;
            }
        }
        return added;
    }

    HashSet<MongoId>? opticMounts;
    HashSet<MongoId>? sideMounts;

    // Mounts that can go into a slot measured as not on top: a rail on top of such a mount (the VSS's Zenit B-3
    // side dovetail, rail sections that also fit side rails) may end up on the side of the weapon.
    HashSet<MongoId> SideMounts(Dictionary<string, Dictionary<string, bool>> topRails)
    {
        var side = new HashSet<MongoId>();
        foreach (var owner in templateTable.Items.Values)
        {
            if (owner.Properties?.Slots is null || !topRails.TryGetValue(owner.Id.ToString(), out var measured)) continue;
            foreach (var slot in owner.Properties.Slots)
            {
                if (slot.Name is null || !measured.TryGetValue(slot.Name, out bool top) || top) continue;
                var filter = slot.Properties?.Filters?.FirstOrDefault()?.Filter;
                if (filter is null) continue;
                foreach (var id in filter) if (IsA(id, Mount)) side.Add(id);
            }
        }
        return side;
    }

    static bool Takes(Slot slot, Func<MongoId, bool> what) =>
        slot.Properties?.Filters?.FirstOrDefault()?.Filter?.Any(what) == true;

    void AddListing(MongoId pvs, JsonObject listing, string name)
    {
        if (!tradersTable.TryGetValue(new MongoId(listing["traderId"]!.GetValue<string>()), out var trader) || trader.Assort is null)
        {
            logger.Warning($"{name} trader missing; item is only on the flea market");
            return;
        }
        var assortId = new MongoId(listing["assortId"]!.GetValue<string>());
        if (trader.Assort.Items.Any(i => i.Id == assortId)) return;
        trader.Assort.Items.Add(new Item
        {
            Id = assortId,
            Template = pvs,
            ParentId = "hideout",
            SlotId = "hideout",
            Upd = new Upd { UnlimitedCount = true, StackObjectsCount = 999999, BuyRestrictionMax = 2, BuyRestrictionCurrent = 0 }
        });
        trader.Assort.BarterScheme[assortId] =
        [
            [new BarterScheme { Count = listing["price"]!.GetValue<double>(), Template = new MongoId(listing["currency"]!.GetValue<string>()) }]
        ];
        trader.Assort.LoyalLevelItems[assortId] = listing["loyalty"]!.GetValue<int>();
    }
}
