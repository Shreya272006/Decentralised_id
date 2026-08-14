const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);

  // --- IssuerRegistry ---
  const IssuerRegistry = await hre.ethers.getContractFactory("IssuerRegistry");
  const issuerRegistry = await IssuerRegistry.deploy(deployer.address);
  await issuerRegistry.waitForDeployment();
  const issuerRegistryAddress = await issuerRegistry.getAddress();
  console.log("IssuerRegistry deployed to:", issuerRegistryAddress);

  // --- CredentialRegistry (depends on IssuerRegistry) ---
  const CredentialRegistry = await hre.ethers.getContractFactory("CredentialRegistry");
  const credentialRegistry = await CredentialRegistry.deploy(deployer.address, issuerRegistryAddress);
  await credentialRegistry.waitForDeployment();
  const credentialRegistryAddress = await credentialRegistry.getAddress();
  console.log("CredentialRegistry deployed to:", credentialRegistryAddress);

  // --- RevocationRegistry ---
  const RevocationRegistry = await hre.ethers.getContractFactory("RevocationRegistry");
  const revocationRegistry = await RevocationRegistry.deploy(deployer.address);
  await revocationRegistry.waitForDeployment();
  const revocationRegistryAddress = await revocationRegistry.getAddress();
  console.log("RevocationRegistry deployed to:", revocationRegistryAddress);

  // Grant the backend service role to the operational wallet used by the
  // FastAPI backend for anchoring transactions (defaults to the deployer
  // in local/dev; override with BACKEND_SERVICE_ADDRESS in production).
  const backendServiceAddress = process.env.BACKEND_SERVICE_ADDRESS || deployer.address;
  const BACKEND_SERVICE_ROLE = await issuerRegistry.BACKEND_SERVICE_ROLE();

  await (await issuerRegistry.grantRole(BACKEND_SERVICE_ROLE, backendServiceAddress)).wait();
  await (await credentialRegistry.grantRole(BACKEND_SERVICE_ROLE, backendServiceAddress)).wait();
  await (await revocationRegistry.grantRole(BACKEND_SERVICE_ROLE, backendServiceAddress)).wait();
  console.log("Granted BACKEND_SERVICE_ROLE to:", backendServiceAddress);

  const deploymentInfo = {
    network: hre.network.name,
    deployer: deployer.address,
    backendServiceAddress,
    contracts: {
      IssuerRegistry: issuerRegistryAddress,
      CredentialRegistry: credentialRegistryAddress,
      RevocationRegistry: revocationRegistryAddress,
    },
    deployedAt: new Date().toISOString(),
  };

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(
    path.join(outDir, `${hre.network.name}.json`),
    JSON.stringify(deploymentInfo, null, 2)
  );
  console.log("Deployment info written to deployments/" + hre.network.name + ".json");

  // Also copy ABIs the backend needs into backend/contracts_abi/ so the
  // Python web3.py connector can load them without recompiling Solidity.
  const abiOutDir = path.join(__dirname, "..", "..", "backend", "contracts_abi");
  fs.mkdirSync(abiOutDir, { recursive: true });
  for (const name of ["IssuerRegistry", "CredentialRegistry", "RevocationRegistry"]) {
    const artifact = await hre.artifacts.readArtifact(name);
    fs.writeFileSync(
      path.join(abiOutDir, `${name}.json`),
      JSON.stringify({ abi: artifact.abi }, null, 2)
    );
  }
  console.log("Contract ABIs exported to backend/contracts_abi/");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
