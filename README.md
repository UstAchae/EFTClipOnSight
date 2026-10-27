# Justachae's Clip-on Sight

SPT 4.1.6 的夹式瞄具模组。它加入四种夹式夜视仪和热像仪，装在倍率白光瞄具前方的导轨上，与白光瞄具同轴使用：通过白光瞄具看到的画面会变成夜视或热成像，倍率仍由白光瞄具提供。

Clip-on night vision and thermal sights for SPT 4.1.6. They mount on the rail in front of a magnified day scope, and the view through that scope becomes night vision or thermal while the scope keeps its own magnification.

## 四个模组

每种夹式瞄具是一个独立的模组，想要哪个装哪个，可以同时装多个。

| 模组 | 物品 | 类型 | 适配白光瞄具 | 实物参数 | 模型 |
|---|---|---|---|---|---|
| `JustachaesClipOnSight-PVS22` | AN/PVS-22 通用夜视瞄具 | 夜视（P43 绿色荧光屏） | 最高 12 倍 | 长 180 mm，0.86 kg，视场 12° | **随模组附带** |
| `JustachaesClipOnSight-PVS30` | AN/PVS-30 夹式狙击夜视瞄具 | 夜视（P45 白色荧光屏） | 最高 20 倍 | 长 244 mm，1.32 kg，视场 9° | **随模组附带** |
| `JustachaesClipOnSight-PVS27` | AN/PVS-27 MUNS 马格南通用夜视瞄具（黑色、沙色） | 夜视（P43 绿色荧光屏） | 3 到 20 倍 | 长 221 mm，1.42 kg，视场 10° | 自行购买，用脚本生成 |
| `JustachaesClipOnSight-UTC` | Trijicon UTC XII 通用夹式热成像瞄具（黑色、沙色） | 白热热成像 | 最高 10 倍 | 长 158 mm，0.57 kg，视场 7.8° | 自行购买，用脚本生成 |

物品都在 Peacekeeper 一级出售，也可以在跳蚤市场买到。

## 安装

1. 从 [Releases](../../releases) 下载想要的模组，比如 `JustachaesClipOnSight-PVS30-<版本>.zip`。
2. 解压到游戏根目录（有 `EscapeFromTarkov.exe` 的那个文件夹）。每个模组会放到两个地方：
   - `SPT_Runtime/user/mods/UstAchae-ClipOnSight-<型号>/`：服务端模组和物品数据，以及模型 bundle 或生成脚本和模板。
   - `BepInEx/plugins/UstAchae-ClipOnSight/`：游戏插件。四个模组用的是同一个插件，装多个时覆盖即可，选"替换"。
3. 启动服务端和游戏。AN/PVS-22 和 AN/PVS-30 装好就能用；AN/PVS-27 和 UTC XII 需要先按下面的步骤生成模型。

卸载时删除对应的 `UstAchae-ClipOnSight-<型号>` 文件夹即可；四个都卸载时再删除 `BepInEx/plugins/UstAchae-ClipOnSight`。删除前请先把这些物品从仓库和角色身上拿掉。

## AN/PVS-27 和 UTC XII：用自己购买的模型生成

这两个模型来自 CGTrader，按其授权条款，模组不附带模型，只附带不含模型的模板（`templates/`）和生成脚本。买了哪个，就能生成哪个；没有生成模型的物品不会出现在游戏里。

| 模组 | 购买链接 | 需要的输入文件 | 脚本 |
|---|---|---|---|
| AN/PVS-27（含沙色） | [CGTrader：PVS27 Magnum Universal Night Sight](https://www.cgtrader.com/3d-models/military/other/pvs27-magnum-universal-night-sight) | `pvs27-magnum-universal-night-sight.zip` | `build_pvs27.py` |
| UTC XII（含沙色） | [CGTrader：UTCx Thermal Weapon Sight](https://www.cgtrader.com/3d-models/military/other/utcx-thermal-weapon-sight) | `utcx-thermal-weapon-sight.zip` | `build_utc.py` |

需要：Python 3.10 或更新版本，并安装依赖：

```
pip install UnityPy numpy Pillow
```

步骤：

1. 把从 CGTrader 下载的 zip 原样放进一个文件夹，**不要解压，文件名保持不变**。
2. 关闭服务端和游戏。
3. 在模组文件夹里运行脚本，参数是放 zip 的文件夹。例如 AN/PVS-27：

   ```
   cd SPT_Runtime/user/mods/UstAchae-ClipOnSight-PVS27
   python build_pvs27.py <放 zip 的文件夹>
   ```

   UTC XII 则是在 `UstAchae-ClipOnSight-UTC` 里运行 `python build_utc.py <放 zip 的文件夹>`。
4. 脚本会把黑色和沙色两个 bundle 生成到 `bundles/`，并写好 `bundles.json`。启动服务端，物品就出现了。

说明：

- **只认指定版本的模型：** 脚本会核对用到的每个文件的 SHA-256。模组是按这一版模型测量和调整的，商店里的模型如果更新过，脚本会提示文件不对，这时请提交 issue。
- **和作者版本一致：** 脚本按作者自己的构建流程处理网格和贴图。在同样的视角下，生成的 bundle 和作者构建的 bundle 渲染出来的平均差异约为 0.5/255，肉眼看不出区别。
- **模板不含模型：** 模板只有预制体、材质、着色器和位置标记，网格和贴图都是空的；生成的 bundle 只在你自己的电脑上，请勿转发。
- **模组更新后要重新生成：** 新版本的模板可能有改动，更新模组后请重新运行一次脚本。

## 功能

- **装在哪里：** 能装在"激光器可以正装在顶上"的导轨槽位上，也就是护木、导轨座、机匣、导气箍、枪托的顶部槽位；不能装在瞄具的镜圈和底座上，也不能装在侧面导轨上。哪些槽位在顶部，是从每个原版物品的预制体里实测槽位位置得出的；其他模组新加的槽位按槽位名和是否接受 NcStar MPR45 来判断。
- **自动定位：** 装上后会自动前后滑动，贴到后方瞄具的物镜前面，换瞄具、换镜圈时会重新贴合，物品图标里也一样。
- **和斜边座互斥：** 带瞄具的 45° 斜边座（如 NcStar MPR45）在夹式瞄具的光路里，两者不能同时装在一把枪上。
- **夜视画面：** 自己实现的像增强管画面，包括读出和散粒噪声、颗粒、固定图案噪声、闪烁、P43 绿色或 P45 白色荧光屏。三款夜视仪按各自公布的参数区分亮度、噪声和颗粒。
- **热成像：** UTC XII 用游戏自带的热成像效果，参数取自 REAP-IR，按 UTC XII 的规格调整（60 Hz、噪声减半、拖影更短、白热）。
- **清晰度随倍率变化：** 夹式瞄具自己的分辨率是固定的，后面的白光瞄具倍率越高，就把它的模糊放得越大，所以画面从低倍起就随倍率逐渐变软（PVS-22 最明显）。超过额定倍率后，画面还会变暗、噪声变多；热像仪会显出传感器的像素格。
- **目镜画面：** 自己枪上的夹式瞄具后面没有倍率瞄具时，从目镜看进去能看到实时的夜视或热成像画面，按实物的 1 倍无焦光路成像：画面和外界同方向，视线偏离光轴超过半视场就被视场光阑挡成黑色，所以瞄准时能看到完整的圆形视场，腰射时只剩一点荧光屏的微光。热成像用游戏自带的热成像处理。画面只在看得见时才渲染，不画阴影。
- **镜片反光：** 物镜和目镜的镀膜玻璃反射所在位置的环境（反射探针），并按实际照到镜片的光源（太阳、灯、手电）出现高光，中间被墙挡住的光源不算。散落在地图里或装在别人枪上的夹式瞄具，目镜就是一块深色镀膜玻璃。
- **没有开关：** 装上就工作，像实物一样，白天使用时把它拆下来。

## 配置

插件设置在 `BepInEx/config/com.ustachae.cliponsight.cfg`：

| 分组 | 项目 | 默认 | 说明 |
|---|---|---|---|
| Night vision | Gain | 30 | 像增强管增益（以 PVS-22 为基准，PVS-27 和 PVS-30 按设计更亮） |
| Night vision | Noise | 1 | 噪声强度，0 为关闭 |

## 模型来源

| 物品 | 来源 | 授权 | 说明 |
|---|---|---|---|
| AN/PVS-22 | [TurboSquid：AN/PVS-22](https://www.turbosquid.com/3d-models/an-pvs-22-519395) | TurboSquid 3D Model License，允许以游戏引擎的专有格式用于游戏模组 | 本模组重新展了 UV、烘焙并重新生成了贴图，加了导轨夹具；随模组附带 |
| AN/PVS-27 | [CGTrader：PVS27 Magnum Universal Night Sight](https://www.cgtrader.com/3d-models/military/other/pvs27-magnum-universal-night-sight) | CGTrader Royalty Free | 含黑色和沙色贴图；不附带，玩家自行购买后用脚本生成 |
| AN/PVS-30 | [3D Military Assets（3DMA）：KAC AN/PVS-30 Night Vision Device](https://www.3dmilitaryassets.com/products/kac-an-pvs-30-night-vision-device) | 3DMA Personal，允许用于免费的塔科夫模组 | 模型由 3DMA（www.3dmilitaryassets.com）制作；随模组附带 |
| Trijicon UTC XII | [CGTrader：UTCx Thermal Weapon Sight](https://www.cgtrader.com/3d-models/military/other/utcx-thermal-weapon-sight) | CGTrader Royalty Free | 原模型是 UTCx，本模组按 UTC XII 的参数使用；含黑色和沙色贴图；不附带，玩家自行购买后用脚本生成 |

模型的版权归各自作者所有。请勿从本模组提取或转发 AN/PVS-22 和 AN/PVS-30 的模型。

## 开发

| 路径 | 内容 |
|---|---|
| `pvs22/ClientSource` | BepInEx 插件（四个模组共用）：瞄具画面效果、目镜画面、镜片光照、自动定位、图标 |
| `pvs22/ServerSource` | SPT 服务端模组：加入物品、导轨槽位、互斥规则、商人；没有 bundle 的物品不加载。`build.sh` 把同一份代码编译成四个模组各自的程序集 |
| `pvs22/UnityProject` | Unity 工程：生成预制体和着色器、打包 bundle（`Assets/Editor`），以及游戏组件的占位脚本（`Assets/PVS22Stubs`） |
| `pvs22/*.py`、`clipons/*.py` | 作者用的完整处理流程：烘焙、网格、贴图、材质、物品数据、导轨测量、安装 |
| `mods.py` | 四个模组各包含哪些物品和 bundle |
| `converter/build_pvs27.py`、`converter/build_utc.py` | 玩家用的生成脚本（各为单个文件，随对应模组发布），由 `converter/make_scripts.py` 从 `converter/parts/` 生成 |
| `converter/make_templates.py` | 从作者构建的 bundle 生成不含模型的模板 |
| `converter/templates/` | 模板 |
| `make_release.py` | 打包四个模组的发布文件 |
| `common/game_refs.py` | 游戏共享着色器和环境贴图的引用 |

作者的完整构建需要 Unity 2022.3.43f1、Python（`UnityPy`、`numpy`、`Pillow`）、Blender、.NET SDK 和 Roslyn 编译器；脚本里的路径按作者自己的目录写死（游戏在 `D:/games/SPT-4.1.6`，本仓库在 `D:/games/SPT-4.1.6/.codex-work/EFTClipOnSight`，Unity 在 `D:/Unity 2022.3.43f1`）。

1. 模型解压到 `pvs22/src` 和 `clipons/src/<pvs27|pvs30|utc>`（路径见 `clipons/items.py`）。
2. PVS-22：`blender -b --factory-startup --python pvs22/blender_bake.py`，再运行 `pvs22/make_textures.py`、`pvs22/prepare_mesh.py`；其他三款运行 `clipons/prepare.py`。
3. 在 Unity 里执行 `PVS22Builder.Build` 和 `ClipOnBuilder.Build`，再运行 `pvs22/finalize_bundle.py` 和 `clipons/finalize_clipons.py`。
4. 物品数据：`pvs22/make_catalog.py`、`clipons/make_catalogs.py`。
5. 编译：`pvs22/build_client.sh`；`pvs22/ServerSource/build.sh`。
6. 生成脚本和模板：`python converter/make_scripts.py`、`python converter/make_templates.py`；发布包：`python make_release.py`。
7. 自己测试时，关闭服务端和游戏后运行 `clipons/install.py`（会安装四个模组）。

`pvs22/top_rails.py` 会从游戏的物品预制体里重新测量导轨槽位，生成 `pvs22/package/db/top_rails.json`；仓库里已经附带测好的结果。

## 授权

本仓库的代码和脚本保留所有权利（All rights reserved）。
