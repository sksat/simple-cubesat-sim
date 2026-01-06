# Tasks

## Current Sprint: Attitude Control Enhancement

### Phase 1: Foundation - Absolute Time & Power System
| Status | Task | Description |
|--------|------|-------------|
| [x] | Absolute time | シミュレーション絶対時刻の導入 |
| [x] | Power simulation | SAP発電・バッテリー消費の模擬 |
| [x] | Battery sizing | 600km SSO での生存可能性検証スクリプト |

### Phase 2: 3-Axis Attitude Control
| Status | Task | Description |
|--------|------|-------------|
| [x] | Target direction types | SUN, EARTH_CENTER, GROUND_STATION, IMAGING_TARGET |
| [x] | Main/Sub axis concept | 2軸指向制御ロジック実装 |
| [x] | Target quaternion calc | DCM→Quaternion計算 |
| [x] | Ground station | 牧之原の座標設定、仰角5度以上で通信可能 |
| [x] | Imaging target | 任意緯度経度の設定 |

### Phase 3: Timeline & Contact
| Status | Task | Description |
|--------|------|-------------|
| [x] | Contact prediction | 次回コンタクト時刻の計算 |
| [x] | Action timeline | 衛星アクションのタイムライン概念 |
| [x] | Imaging preset | コンタクトからN分後の撮影地点 |

### Phase 4: UI Enhancement
| Status | Task | Description |
|--------|------|-------------|
| [ ] | Satellite status | 左上にモード・通信・電力・軸誤差表示 |
| [ ] | Move center button | 右上に center 選択ボタン移動 |
| [ ] | 3-axis control UI | main/sub軸の方向・指向設定画面 |

### Phase 5: Visualization
| Status | Task | Description |
|--------|------|-------------|
| [ ] | Realistic Earth scale | satellite center での地球サイズを現実比率に |
| [ ] | Camera simulation | -Z方向カメラ映像の表示 |
| [ ] | Imaging error display | 撮影目標とのズレ表示 |

---

## Completed
| Date | Task | Commit |
|------|------|--------|
| 2026-01-06 | TLE-based orbit propagation | 9a081f4 |
| 2026-01-06 | TLE API integration | bdfdb8e |
| 2026-01-06 | Increased tumbling rate | a5c213d |
| 2026-01-06 | Development lessons documentation | 6e00671 |

---

## Notes

### Main/Sub Axis Algorithm
1. main_target_direction → ECI方向ベクトル計算
2. sub_target_direction → ECI方向ベクトル計算
3. sub ベクトルを main に直交化 (main 優先)
4. DCM計算: dcm_eci_to_body = dcm_target_to_body × transpose(dcm_target_to_eci)
5. DCM → Quaternion 変換

### Target Directions
- SUN: 太陽方向
- EARTH_CENTER: 地心方向 (Nadir)
- GROUND_STATION: 地上局方向 (牧之原固定)
- IMAGING_TARGET: 撮影地点方向 (任意LLA)

### Ground Station
- Location: 牧之原 (34.74°N, 138.22°E)
- Visibility: elevation > 5°
- Fast ECI-to-ECEF: GMST-based rotation (~2000x faster than Astropy)
