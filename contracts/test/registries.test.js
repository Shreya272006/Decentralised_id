const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Decentralized Identity Registries", function () {
  let issuerRegistry, credentialRegistry, revocationRegistry;
  let admin, backendService, outsider;

  beforeEach(async function () {
    [admin, backendService, outsider] = await ethers.getSigners();

    const IssuerRegistry = await ethers.getContractFactory("IssuerRegistry");
    issuerRegistry = await IssuerRegistry.deploy(admin.address);
    await issuerRegistry.waitForDeployment();

    const CredentialRegistry = await ethers.getContractFactory("CredentialRegistry");
    credentialRegistry = await CredentialRegistry.deploy(admin.address, await issuerRegistry.getAddress());
    await credentialRegistry.waitForDeployment();

    const RevocationRegistry = await ethers.getContractFactory("RevocationRegistry");
    revocationRegistry = await RevocationRegistry.deploy(admin.address);
    await revocationRegistry.waitForDeployment();

    const role = await issuerRegistry.BACKEND_SERVICE_ROLE();
    await issuerRegistry.connect(admin).grantRole(role, backendService.address);
    await credentialRegistry.connect(admin).grantRole(role, backendService.address);
    await revocationRegistry.connect(admin).grantRole(role, backendService.address);
  });

  describe("IssuerRegistry", function () {
    it("anchors and approves an issuer", async function () {
      const refId = ethers.keccak256(ethers.toUtf8Bytes("issuer-1"));
      const hash = ethers.keccak256(ethers.toUtf8Bytes("issuer-profile-commitment"));

      await issuerRegistry.connect(backendService).anchorRecord(hash, refId);
      expect(await issuerRegistry.isApprovedIssuer(refId)).to.equal(false);

      await issuerRegistry.connect(admin).approveIssuer(refId);
      expect(await issuerRegistry.isApprovedIssuer(refId)).to.equal(true);
    });

    it("blocks a previously approved issuer", async function () {
      const refId = ethers.keccak256(ethers.toUtf8Bytes("issuer-2"));
      const hash = ethers.keccak256(ethers.toUtf8Bytes("commitment"));
      await issuerRegistry.connect(backendService).anchorRecord(hash, refId);
      await issuerRegistry.connect(admin).approveIssuer(refId);
      await issuerRegistry.connect(admin).blockIssuer(refId);
      expect(await issuerRegistry.isApprovedIssuer(refId)).to.equal(false);
    });

    it("rejects anchoring from a non-backend-service account (access control)", async function () {
      const refId = ethers.keccak256(ethers.toUtf8Bytes("issuer-3"));
      const hash = ethers.keccak256(ethers.toUtf8Bytes("commitment"));
      await expect(issuerRegistry.connect(outsider).anchorRecord(hash, refId)).to.be.reverted;
    });
  });

  describe("CredentialRegistry", function () {
    it("anchors a credential and verifies integrity", async function () {
      const refId = ethers.keccak256(ethers.toUtf8Bytes("credential-1"));
      const hash = ethers.keccak256(ethers.toUtf8Bytes("claims-commitment"));

      await credentialRegistry.connect(backendService).anchorRecord(hash, refId);

      const [storedHash, exists] = await credentialRegistry.getRecord(refId);
      expect(exists).to.equal(true);
      expect(storedHash).to.equal(hash);
      expect(await credentialRegistry.verifyIntegrity(refId, hash)).to.equal(true);

      const tamperedHash = ethers.keccak256(ethers.toUtf8Bytes("tampered"));
      expect(await credentialRegistry.verifyIntegrity(refId, tamperedHash)).to.equal(false);
    });

    it("prevents double-anchoring the same credential reference", async function () {
      const refId = ethers.keccak256(ethers.toUtf8Bytes("credential-2"));
      const hash = ethers.keccak256(ethers.toUtf8Bytes("commitment"));
      await credentialRegistry.connect(backendService).anchorRecord(hash, refId);
      await expect(
        credentialRegistry.connect(backendService).anchorRecord(hash, refId)
      ).to.be.revertedWith("CredentialRegistry: already anchored");
    });

    it("requires an approved issuer for anchorRecordWithIssuer", async function () {
      const issuerRef = ethers.keccak256(ethers.toUtf8Bytes("issuer-unapproved"));
      const credRef = ethers.keccak256(ethers.toUtf8Bytes("credential-3"));
      const hash = ethers.keccak256(ethers.toUtf8Bytes("commitment"));

      await expect(
        credentialRegistry.connect(backendService).anchorRecordWithIssuer(hash, credRef, issuerRef)
      ).to.be.revertedWith("CredentialRegistry: issuer not approved");
    });
  });

  describe("RevocationRegistry", function () {
    it("anchors a revocation and allows admin reversal", async function () {
      const refId = ethers.keccak256(ethers.toUtf8Bytes("credential-1"));
      const hash = ethers.keccak256(ethers.toUtf8Bytes("revocation-commitment"));

      await revocationRegistry.connect(backendService).anchorRecord(hash, refId);
      expect(await revocationRegistry.isRevoked(refId)).to.equal(true);

      await revocationRegistry.connect(admin).reverseRevocation(refId);
      expect(await revocationRegistry.isRevoked(refId)).to.equal(false);
    });
  });
});
