# PE-Reborn Android 17 — row 171: NXP PN5xx HIDL service implementations

**Audited 2026-11-07.** Objective: a new **independent** AOSP17-based PixelExperience-Reborn ROM; future target **POCO F5 Pro / Redmi K60 (mondrian, SM8475)**. This document is a **pinned-source/service-boundary audit**, **not** a compile, boot, NFC HAL runtime or device certification result.

## Decision

**DO NOT install or import `vendor/nxp/opensource/pn5xx/hidlimpl` in the AOSP17 manifest, and do not select either `vendor.nxp.hardware.nfc@1.2-service` or `vendor.nxp.hardware.nfc@2.0-service` for the new product.**

These binaries register a **system NFC HIDL 1.2** implementation (the `2.0` directory is NXP's *vendor extension* version, not NFC AIDL V2) plus old vendor HIDL services and depend on the historical PN5xx native library `nfc_nci.nqx.default.hw` (audited row 170). They cannot be assumed to coexist with or replace Android17 NFC Mainline's selected NFC AIDL `INfc/default` service.

Keep the official AOSP17 `platform/hardware/nxp/nfc`, `platform/packages/modules/Nfc`, `platform/system/secure_element`, and the system NFC stable AIDL owner. The official NXP AOSP17 tree already contains the modern frozen `vendor.nxp.nxpnfc_aidl` extension (verified row 169). NXP Android17 **17.07.00** provides NFC **AIDL V2** `INfc/default` and **vendor AIDL V1** `INxpNfc/default`; consider only justified current-source changes against the existing official HAL, once actual mondrian controller/firmware/SE requirements and platform compatibility are known. Do not overwrite official NFC Soong module namespace with a duplicate fork.

## Evidence and exact pins

- Historical PE `vendor_nxp_opensource_pn5xx_hidlimpl` `seventeen`: commit **`a210f5e90e6ce7326f0cc5fcfda40ca63d55373e`**, git tree **`8dce70df4a27e314065ff18433b6162a8ff41fd4`**, last update **2020-06-22**. Contains 20 tracked blobs, 1.2/default and 2.0/default.
- Historical dependent HAL library (row 170): `vendor_nxp_opensource_pn5xx_halimpl` `seventeen`, commit `36cf9d4af781d5aaa673227e5c06cf3e34ffa647`, tree `56d5e2b919750d354443a1052977e5f70fe2b0ad`. Its root `Android.bp` declares `nfc_nci.nqx.default.hw` and related HIDL/SE stack. **Both** archives are required to reconstruct the old graph, not just this 20-file wrapper.
- Official Android17 NFC HAL: `platform/hardware/nxp/nfc` tag `android-17.0.0_r1`, commit **`68931d93d3b2ccfc71553cb03088fe5d6fb5dd30`**, tree **`8386a3c67e07f5fe492c92d1888c256bbc37d48b`**. Has `android.hardware.nfc-service.nxp` and `intf/nxpnfc/aidl` stable vendor AIDL.
- Current vendor reference: `NXPNFCProject/nfcandroid_nfc_hidlimpl` `br_ar_17_aosp_mainline`, commit **`debec247cea5570d259db3138124201e3769a728`**, tree **`31be748946aaf58dcf86034804db69c53a4ac3a7`**; release **17.07.00** targets Android `android-17.0.0_r1` and lists NXP PN557/PN560/SN100/SN110/SN220/SN300 families. This is **not evidence** of the installed mondrian NFC part.

### Two archived service variants — not equivalent to NFC AIDL V2

| Old package | Soong / init source | Services registered in a single HIDL process | Dependencies |
| --- | --- | --- | --- |
| `vendor.nxp.hardware.nfc@1.2-service` | `1.2/default/Android.bp` and `1.2/default/vendor.nxp.hardware.nfc@1.2-service.rc` | `android.hardware.nfc::V1_2::INfc` and `vendor.nxp.hardware.nfc::V1_1::INqNfc` using `registerAsService()` | `nfc_nci.nqx.default.hw`, `libhidlbase`, NFC HIDL 1.0/1.1/1.2, NXP HIDL 1.0/1.1 |
| `vendor.nxp.hardware.nfc@2.0-service` | `2.0/default/Android.bp` and `2.0/default/vendor.nxp.hardware.nfc@2.0-service.rc` | **Still `android.hardware.nfc::V1_2::INfc`**, vendor `vendor.nxp.hardware.nfc::V2_0::INqNfc`, and `vendor.nxp.nxpnfclegacy::V1_0::INxpNfcLegacy` | Same old PN5xx HAL library; NFC HIDL 1.0/1.1/1.2 + NXP HIDL 2.0/legacy 1.0 |
| Both services | init `service nqnfc_1_2_hal_service` or `service nqnfc_2_0_hal_service`, `class hal`, `user nfc`, `group nfc` | Non-lazy HIDL hwbinder and `configureRpcThreadpool(1,true)`; binary runs under vendor `/vendor/bin/hw/` | **Not AIDL** and not compatible by renaming the module or changing only `.rc` |

The 2.0 variant's `service.cpp` treats failure of the main system NFC HIDL registration as fatal but only logs failures for the two NXP vendor service registrations. Thus the vendor interfaces **could remain unavailable while the process stays alive**; this is an integration/observability risk, not proof of an exploitable vulnerability.

Other source-level differences matter: archived 2.0 `NqNfc::resetEse(uint64_t /* resetType */)` explicitly discards the passed reset type, using parameterless `phNxpNciHal_resetEse()`, whereas current NXP Android17 AIDL `NxpNfc::resetEse(int64_t resetType,...)` passes that value to `phNxpNciHal_resetEse(resetType)`. Do not map these APIs as functionally identical without inspecting controller behavior. The 1.2 vs 2.0 `Nfc::factoryReset()` code also differs (NFCEE session reset vs `phNxpNciHal_do_factory_reset()`), so swapping old variants is not an innocuous build-name change.

### Modern system HAL and vendor-extension boundary

Current NXP Android17 `snxxx/Android.bp` declares `android.hardware.nfc2-service.nxp` with `android.hardware.nfc-V2-ndk`, `vendor.nxp.nxpnfc_aidl-V1-ndk`, `vintf_fragments: ["aidl/2.0/nfc2-service-nxp.xml"]`. The fragment uses two different interfaces:

1. `android.hardware.nfc` **AIDL V2** `INfc/default`, **one** system NFC hardware service.
2. `vendor.nxp.nxpnfc_aidl` **frozen VINTF-stable AIDL V1** `INxpNfc/default`, optional vendor extension with four methods.

Current `snxxx/aidl/2.0/main.cpp` uses NDK Binder service registration, not old HIDL `registerAsService()`. The *official* AOSP17 HAL source already provides the NXP vendor AIDL package; the actual selected version of the system HAL/service on a real PE-Reborn product must be established by a compatible device/product build, **not** assumed from a repository's filenames.

AOSP17 NFC Mainline `packages/modules/Nfc` and `com.android.nfcservices` have their own system/JNI/APEX contract. Do not mix archived PN5xx HIDL product packages or vendor fragments with a new AIDL HAL without a verified explicit compat path and comprehensive source/vendor/SE policy review.

## Device-specific and safety gates for mondrian

1. Confirm the actual mondrian NFC controller, firmware, kernel node, vendor NFC blob dependencies, eSE/UICC wiring and real VINTF fragment via trustworthy device-specific evidence. **Do not infer PN557/PN81T/SN100 from family lists or copy another ROM tree**. LF52406 LineageOS trees may be *exceptional last-resort read-only sources*, not ROM implementation baselines.
2. Select a single NFC HAL source and corresponding init/VINTF: one `INfc/default`. Avoid starting both old HIDL service and current AIDL service and avoid conflicting FCM or SELinux domains.
3. Check stable AIDL frozen API/hash, NDK/Soong service links, current NXP vendor extension, Binder permissions/SELinux and SE authorization (especially reset and vendor parameter setters). No permissive policy or blanket device-node permissions.
4. Validate exact NFCC firmware and RF settings only through manufacturer-supported setup. No eSE factory reset, firmware flash or JCOP/LS update without a justified and safe procedure.
5. Perform AOSP17 Soong/APEX build, VINTF/FCM, SELinux neverallow, NFC CTS/VTS and real NFC read/write, HCE/card routing, SE/OMAPI, sleep/resume, reboots, recovery and power/latency measurements before any functional or support claim.

## Work scope

Audit-only branch: pinned historical/official/vendor source comparison; source gate and GitHub Actions; active PE-Reborn manifest rejects the archived HIDL checkout/name and tests old HAL owner replacement. `default.xml`, kernel, vendor firmware, device/product trees and original `seventeen` are **unchanged**. Full Android17 builds, actual HAL/SE operation and mondrian hardware results remain **OPEN**.
