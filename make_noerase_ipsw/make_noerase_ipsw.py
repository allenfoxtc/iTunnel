import os, zipfile, sys, tempfile, shutil, plistlib, traceback


def recursive_zip(zipf, basePath, zipPath=""):
    for fname in os.listdir(os.path.join(basePath, zipPath)):
        izPath = os.path.join(zipPath, fname)
        iPath = os.path.join(basePath, izPath)
        if os.path.isfile(iPath):
            zipf.write(iPath, izPath, zipfile.ZIP_DEFLATED)
        elif os.path.isdir(iPath):
            recursive_zip(zipf, basePath, izPath)


def fix_ramdisk_dict(ramdisks):
    ramdisks["User"] = ramdisks["Update"]
    del ramdisks["Update"]


def fix_build_manifest(ipswDir):
    buildManifestPlist = os.path.join(ipswDir, "BuildManifest.plist")
    if not os.path.exists(buildManifestPlist):
        print "No BuildManifest file"
        return

    buildManifest = plistlib.readPlist(buildManifestPlist)
    buildIdentities = buildManifest["BuildIdentities"]

    assert len(buildIdentities) % 2 == 0

    # fix for ios 10
    restoreIndex = []
    updateIndex = []

    for i in range(len(buildIdentities)):
        biInfo = buildIdentities[i]["Info"]
        # print "Build identity %i: %s" % (i, biInfo["RestoreBehavior"])
        if biInfo["RestoreBehavior"] == "Erase":
            restoreIndex.append(i)
        elif biInfo["RestoreBehavior"] == "Update":
            updateIndex.append(i)

    assert (len(restoreIndex) + len(updateIndex) == len(buildIdentities))

    restoreIndex.reverse()

    for restoreindex in restoreIndex:
        buildIdentities.pop(restoreindex)

    for k in range(len(buildIdentities)):
        updateBiInfo = buildIdentities[k]["Info"]

        assert "Update" == updateBiInfo["RestoreBehavior"]
        updateBiInfo["RestoreBehavior"] = "Erase"

        assert "UpdateRamDisk" == updateBiInfo["VariantContents"]["RestoreRamDisk"]
        updateBiInfo["VariantContents"]["RestoreRamDisk"] = "CustomerRamDisk"

    plistlib.writePlist(buildManifest, buildManifestPlist)

    print "Written BuildManifest.plist"


def make_upgrade_only(ipswDir):
    restorePlist = os.path.join(ipswDir, "Restore.plist")
    restore = plistlib.readPlist(restorePlist)

    restoreRamDisks = restore["RestoreRamDisks"]

    print "Update RD: %s, restore RD: %s" % (restoreRamDisks["Update"], restoreRamDisks["User"])

    updateRamdisk = restoreRamDisks["Update"]
    restoreRamdisk = restoreRamDisks["User"]

    os.remove(os.path.join(ipswDir, restoreRamdisk))
    print "Deleted RESTORE ramdisk file: %s" % restoreRamdisk

    fix_ramdisk_dict(restoreRamDisks)

    for platformName, platInfo in restore["RamDisksByPlatform"].items():
        print "Platform: %s, update RD: %s, restore RD: %s" % (platformName, platInfo["Update"], platInfo["User"])
        fix_ramdisk_dict(platInfo)

    plistlib.writePlist(restore, restorePlist)
    print "Written Restore.plist"

    fix_build_manifest(ipswDir)


def has_build_manifest(ipsw):
    try:
        ipsw.getinfo("BuildManifest.plist")
        return True
    except KeyError:
        return False


def ipsw_info(ipswDir):
    buildManifestPlist = os.path.join(ipswDir, "BuildManifest.plist")
    if not os.path.exists(buildManifestPlist):
        return

    buildManifest = plistlib.readPlist(buildManifestPlist)
    print "ProductVersion: %s, ProductBuildVersion: %s, SupportedProductTypes: %s" % (
        buildManifest["ProductVersion"], buildManifest["ProductBuildVersion"], buildManifest["SupportedProductTypes"])


def main():
    if len(sys.argv) <= 1:
        print "Usage: %s <ipsw file>" % sys.argv[0]
        return

    origIpsw = sys.argv[1]

    print "Original IPSW file: %s" % origIpsw
    if not zipfile.is_zipfile(origIpsw):
        print "Not a valid IPSW file:", origIpsw
        return
    try:
        ipsw = zipfile.ZipFile(origIpsw)
    except:
        print "Failed to open", origIpsw
        return

    if not has_build_manifest(ipsw):
        print "IPSW for an unsupported device: BuildManifest.plist missing!"
        return

    tempDir = tempfile.mkdtemp()
    print "Unpacking to %s ..." % tempDir
    ipsw.extractall(tempDir)
    ipsw.close()

    ipsw_info(tempDir)

    make_upgrade_only(tempDir)

    newPath = os.path.split(origIpsw)
    newIpsw = os.path.join(newPath[0], "UPG_" + newPath[1])
    print "Packing upgrade-only IPSW to %s ..." % newIpsw
    ipswUp = zipfile.ZipFile(newIpsw, mode='w', allowZip64=True)
    recursive_zip(ipswUp, tempDir)
    ipswUp.close()

    print "Cleaning up"
    shutil.rmtree(tempDir)


if __name__ == '__main__':
    try:
        main()
        print
        print "Press Enter to exit."
        blah = raw_input()
    except:
        traceback.print_exc()
        print >> sys.stderr
        print >> sys.stderr, "Press Enter to exit."
        blah = raw_input()
