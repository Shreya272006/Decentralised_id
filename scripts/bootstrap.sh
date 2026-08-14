#!/usr/bin/env bash
# Convenience bootstrap: deploys contracts and seeds the database against an
# already-running `docker-compose up` stack. Run from the project root:
#   ./scripts/bootstrap.sh
set -euo pipefail

echo "==> Deploying smart contracts to the local Hardhat node..."
docker-compose exec -T hardhat-node npx hardhat run scripts/deploy.js --network localhost

echo ""
echo "==> Contracts deployed. Copy the printed addresses into your .env as:"
echo "    CREDENTIAL_REGISTRY_ADDRESS, REVOCATION_REGISTRY_ADDRESS, ISSUER_REGISTRY_ADDRESS"
echo "    then run: docker-compose restart backend"
read -p "Press Enter once you've updated .env and restarted the backend..." _

echo "==> Seeding the database with demo accounts and credentials..."
docker-compose exec -T backend python -m scripts.seed_db

echo ""
echo "==> Done. Visit http://localhost:3000"
