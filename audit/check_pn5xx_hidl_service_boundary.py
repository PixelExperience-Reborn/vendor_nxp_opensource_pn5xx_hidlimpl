#!/usr/bin/env python3
"""PE-Reborn Android17 row171: NFC HIDL 1.2 / NXP HIDL vs NFC AIDL service.

Pin three historical/current trees and the dependent old HAL source.
SOURCE ONLY: no Soong, VINTF assembly, SELinux or actual device operation.
"""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

OLD_SHA = "a210f5e90e6ce7326f0cc5fcfda40ca63d55373e"
OLD_TREE = "8dce70df4a27e314065ff18433b6162a8ff41fd4"
OLD_IMPL_SHA = "36cf9d4af781d5aaa673227e5c06cf3e34ffa647"
OLD_IMPL_TREE = "56d5e2b919750d354443a1052977e5f70fe2b0ad"
AOSP_SHA = "68931d93d3b2ccfc71553cb03088fe5d6fb5dd30"
AOSP_TREE = "8386a3c67e07f5fe492c92d1888c256bbc37d48b"
NXP_SHA = "debec247cea5570d259db3138124201e3769a728"
NXP_TREE = "31be748946aaf58dcf86034804db69c53a4ac3a7"
OLD_PATH = "vendor/nxp/opensource/pn5xx/hidlimpl"
OLD_NAME = "vendor_nxp_opensource_pn5xx_hidlimpl"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True,
        stderr=subprocess.PIPE).strip()


def pin(root, ref, sha, tree, label):
    actual = git(root, "rev-parse", f"{ref}^{{commit}}")
    require(actual == sha, f"{label} SHA mismatch: {actual}")
    actual_tree = git(root, "rev-parse", f"{actual}^{{tree}}")
    require(actual_tree == tree,
            f"{label} tree mismatch: {actual_tree}")
    return actual


def show(repo, rev, filename):
    return git(repo, "show", f"{rev}:{filename}")


def legacy_services(root):
    ref = pin(root, "refs/remotes/origin/seventeen",
              OLD_SHA, OLD_TREE, "2020 PN5xx HIDL wrapper")
    files = git(root, "ls-tree", "-r", "--name-only", ref).splitlines()
    require(len(files) == 20, "2020 PN5xx service source set changed")
    for version, module, ext in (
        ("1.2", "vendor.nxp.hardware.nfc@1.2-service",
         "vendor.nxp.hardware.nfc@1.1"),
        ("2.0", "vendor.nxp.hardware.nfc@2.0-service",
         "vendor.nxp.hardware.nfc@2.0"),
    ):
        bp = show(root, ref, f"{version}/default/Android.bp")
        service = show(root, ref, f"{version}/default/service.cpp")
        rc = show(root, ref,
                  f"{version}/default/{module}.rc")
        require(f'name: "{module}"' in bp
                and f'init_rc: ["{module}.rc"]' in bp
                and 'defaults: ["hidl_defaults"]' in bp
                and 'vendor: true' in bp
                and '"nfc_nci.nqx.default.hw"' in bp
                and '"android.hardware.nfc@1.2"' in bp
                and f'"{ext}"' in bp,
                f"2020 PN5xx {version} Soong HIDL dependencies drift")
        require("using android::hardware::nfc::V1_2::INfc;" in service
                and "configureRpcThreadpool(1, true" in service
                and "nfc_service->registerAsService()" in service
                and "nq_nfc_service->registerAsService()" in service
                and "joinRpcThreadpool();" in service,
                f"2020 PN5xx {version} HIDL service registration drift")
        require(f"vendor::nxp::hardware::nfc::V{ext[-3:].replace('.', '_')}::INqNfc"
                in service, f"old {version} vendor INqNfc version drift")
        require(f"/vendor/bin/hw/{module}" in rc
                and "class hal" in rc
                and "user nfc" in rc and "group nfc" in rc,
                f"old {version} NFC init service changed")
    svc_v1 = show(root, ref, "1.2/default/service.cpp")
    svc_v2 = show(root, ref, "2.0/default/service.cpp")
    require("INxpNfcLegacy" not in svc_v1,
            "old 1.2 service unexpectedly now provides NXP legacy interface")
    require("INxpNfcLegacy" in svc_v2
            and "nxp_nfc_legacy_service->registerAsService()" in svc_v2
            and 'ALOGE_IF(status != OK' in svc_v2,
            "old 2.0 NXP legacy registration/failure logic drift")
    bp_v2 = show(root, ref, "2.0/default/Android.bp")
    require('"vendor.nxp.nxpnfclegacy@1.0"' in bp_v2
            and '"NxpNfcLegacy.cpp"' in bp_v2,
            "old 2.0 NXP legacy dependency drift")
    old_vendor_impl = show(root, ref, "2.0/default/NqNfc.cpp")
    require("NqNfc::resetEse(uint64_t /* resetType */)" in old_vendor_impl
            and "phNxpNciHal_resetEse();" in old_vendor_impl,
            "old 2.0 resetEse ignored parameter behavior changed")
    legacy = show(root, ref, "2.0/default/NxpNfcLegacy.cpp")
    require("NxpNfcLegacy::nciTransceive(" in legacy
            and "phNxpNciHal_nciTransceive" in legacy,
            "old low-level NCI passthrough changed")
    v1nfc = show(root, ref, "1.2/default/Nfc.cpp")
    v2nfc = show(root, ref, "2.0/default/Nfc.cpp")
    require("phNxpNciHal_reset_nfcee_session(false);" in v1nfc
            and "phNxpNciHal_do_factory_reset();" in v2nfc,
            "old 1.2 vs 2.0 factoryReset divergence changed")
    print("PASS: exact old PN5xx HIDL NFC1.2 service and NXP1.1/V2 variants pinned")
    print("PASS: old 2.0 registers legacy NCI vendor service and ignores eSE reset type")
    print("PASS: old 1.2/2.0 factory-reset semantic divergence pinned")


def legacy_native_dependency(root):
    ref = pin(root, "refs/remotes/origin/seventeen",
              OLD_IMPL_SHA, OLD_IMPL_TREE, "2021 PN5xx native implementation")
    bp = show(root, ref, "Android.bp")
    require('name: "nfc_nci.nqx.default.hw"' in bp
            and '"vendor.nxp.hardware.nfc@2.0"' in bp
            and '"vendor.nxp.nxpnfclegacy@1.0"' in bp,
            "historical HIDL service native PN5xx dependency changed")
    native = show(root, ref, "halimpl/src/halLibnfc/src/Android.bp")
    require('name: "hal_libnfc"' in native
            and '"libhidlbase"' in native,
            "historical HIDL service separate NFA/NCI layer changed")
    print("PASS: old 2020 service requires separately pinned 2021 HIDL HAL/stack")


def official_hal(root):
    ref = pin(root, "refs/tags/android-17.0.0_r1",
              AOSP_SHA, AOSP_TREE, "official AOSP17 NXP HAL")
    bp = show(root, ref, "snxxx/Android.bp")
    vendor = show(root, ref, "intf/nxpnfc/aidl/Android.bp")
    api = show(root, ref,
               "intf/nxpnfc/aidl/vendor/nxp/nxpnfc_aidl/INxpNfc.aidl")
    require('name: "android.hardware.nfc-service.nxp"' in bp,
            "official AOSP17 NFC HAL module name changed")
    require('name: "vendor.nxp.nxpnfc_aidl"' in vendor
            and 'stability: "vintf"' in vendor
            and "ndk: {" in vendor,
            "official AOSP17 vendor NFC AIDL contract changed")
    for api_name in ("getVendorParam(", "setVendorParam(", "resetEse(",
                     "setNxpTransitConfig("):
        require(api_name in api,
                "official NXP AIDL vendor API changed: " + api_name)
    print("PASS: official AOSP17 already owns HAL and NXP VINTF-stable AIDL")


def modern_nxp(root):
    ref = pin(root, "refs/remotes/origin/br_ar_17_aosp_mainline",
              NXP_SHA, NXP_TREE, "NXP Android17 17.07.00")
    bp = show(root, ref, "snxxx/Android.bp")
    vintf = ET.fromstring(
        show(root, ref, "snxxx/aidl/2.0/nfc2-service-nxp.xml"))
    main = show(root, ref, "snxxx/aidl/2.0/main.cpp")
    impl = show(root, ref, "snxxx/extns/impl/nxpnfc/aidl/NxpNfc.cpp")
    assert_modules = (
        'name: "android.hardware.nfc2-service.nxp"',
        '"android.hardware.nfc-V2-ndk"',
        '"vendor.nxp.nxpnfc_aidl-V1-ndk"',
        'vintf_fragments: ["aidl/2.0/nfc2-service-nxp.xml"]',
    )
    for val in assert_modules:
        require(val in bp, "current NXP NFC AIDL2 service drift: " + val)
    declarations = {(h.findtext("name"), h.findtext("version"),
                     h.findtext("fqname"), h.get("format"))
                    for h in vintf.findall("hal")}
    require(declarations == {
        ("android.hardware.nfc", "2", "INfc/default", "aidl"),
        ("vendor.nxp.nxpnfc_aidl", None, "INxpNfc/default", "aidl")
    }, "modern NXP AIDL V2 + vendor AIDL V1 VINTF changed")
    require("AServiceManager_addService(" in main
            and "startNxpNfcAidlService()" in main,
            "current NXP NDK Binder registration changed")
    require("NxpNfc::resetEse(int64_t resetType" in impl
            and "phNxpNciHal_resetEse(resetType)" in impl,
            "modern AIDL eSE reset type handling changed")
    print("PASS: pinned current NXP Android17 uses NFC AIDL V2 + vendor AIDL V1")
    print("PASS: old HIDL resetEse ignored resetType; modern NXP AIDL passes it")


def manifest_guard(root):
    root = Path(root)
    e = ET.parse(root / "default.xml").getroot()
    require(len(e) == 1 and
            e[0].get("name") == "aosp17_pe_p2_kernel_configs.xml",
            "active default AOSP17 stage changed")
    p = ET.parse(root / "aosp17_pe_bootstrap.xml").getroot()
    owner = {n.get("path"): n.get("name") for n in p.findall("project")}
    for path, expected in (
        ("hardware/nxp/nfc", "platform/hardware/nxp/nfc"),
        ("packages/modules/Nfc", "platform/packages/modules/Nfc"),
        ("system/secure_element", "platform/system/secure_element"),
    ):
        require(owner.get(path) == expected,
                f"official NFC owner changed at {path}")
    require(OLD_PATH not in owner and OLD_NAME not in owner.values(),
            "legacy HIDL NFC service accidentally activated")
    validator = (root / "tools/validate_aosp17_base_profiles.py").read_text()
    tests = (root / "tools/test_aosp17_manifest_entrypoint.py").read_text()
    require(f'if "{OLD_PATH}" in projects:' in validator
            and f'"{OLD_NAME}"' in validator,
            "row 171 old HIDL NFC service path/name guard missing")
    for name in (
        "test_archived_pn5xx_hidl_service_cannot_enter_android17",
        "test_archived_pn5xx_hidl_service_cannot_replace_aosp17_hal",
    ):
        require(f"def {name}(" in tests,
                f"row 171 manifest negative test missing: {name}")
    subprocess.run(
        [sys.executable, str(root / "tools/validate_aosp17_base_profiles.py")],
        check=True, cwd=root)
    print("PASS: all 25 AOSP17 source profile owners and row 171 guards")


def main():
    require(len(sys.argv) == 6, "Usage: checker OLD_HIDL OLD_IMPL AOSP17_NXP"
            " MODERN_NXP PE_MANIFEST")
    roots = [Path(s).resolve() for s in sys.argv[1:]]
    require(all(x.is_dir() for x in roots),
            "one or more source checkouts are missing")
    legacy_services(roots[0])
    legacy_native_dependency(roots[1])
    official_hal(roots[2])
    modern_nxp(roots[3])
    manifest_guard(roots[4])
    print("PASS: row 171 old PN5xx HIDL service versus modern AOSP17 NFC boundary")
    print("NOT TESTED: device Soong, APEX, SEPolicy, VINTF, NFC or mondrian")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ET.ParseError, ValueError,
            subprocess.CalledProcessError) as err:
        print("FAIL:", err, file=sys.stderr)
        sys.exit(1)
