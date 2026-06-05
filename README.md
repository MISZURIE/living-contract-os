# LivingContract OS

> AI-Governed Self-Evolving Smart Contract Engine

**"Not 'AI writes your contract' - but 'AI manages your contract within rules you set.'"**

The world's first open-source composable framework for parameterized, AI-governed smart contracts with ZK-verified decisions and on-chain audit trails.

---

## Architecture

```
[Market Data] → [AI Agent Pipeline] → [Mock ZK Proof] → [Sepolia On-Chain] → [Dashboard]
                    5 Agents                ECDSA sig          LivingBase.sol      Next.js
                  (Python/LangGraph)       (EZKL in prod)     + AuditLog          + FastAPI
```

### 4 Layers

| Layer | Technology | Purpose |
|---|---|---|
| On-Chain Core | Solidity 0.8.28 + OpenZeppelin | Single source of truth, policy enforcement |
| ZK/Proof | MockZKVerifier (ECDSA) → EZKL Groth16 in prod | Cryptographic attestation |
| AI Agents | Python + GPT-4o + LangGraph | Policy monitoring, proposal, execution |
| SDK / API | FastAPI + Next.js | Developer access, demo dashboard |

---

## Quick Start

### Prerequisites

- Node.js 22+
- Python 3.11+
- Docker + Docker Compose
- [Foundry](https://getfoundry.sh/) (`curl -L https://foundry.paradigm.xyz | bash`)
- Sepolia ETH ([faucet](https://sepoliafaucet.com))

### 1. Clone & configure

```bash
git clone https://github.com/MISZURIE/living-contract-os
cd living-contract-os
cp .env.example .env
# Fill in .env with your keys
```

### 2. Install Foundry dependencies

```bash
cd packages/contracts
forge install foundry-rs/forge-std
forge install OpenZeppelin/openzeppelin-contracts
forge install OpenZeppelin/openzeppelin-contracts-upgradeable
```

### 3. Run tests

```bash
cd packages/contracts
forge test -vv
```

### 4. Deploy to Sepolia

```bash
cd packages/contracts
forge script script/Deploy.s.sol --rpc-url $RPC_URL --broadcast --verify
# Copy deployed addresses into .env
```

### 5. Start local stack

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Redis | localhost:6379 |

---

## Project Structure

```
living-contract-os/
├── packages/
│   ├── contracts/          # Foundry — Solidity smart contracts
│   │   ├── src/
│   │   │   ├── LivingBase.sol          # Abstract base — policy enforcement
│   │   │   ├── PolicyRegistry.sol      # Boundary storage
│   │   │   ├── MockZKVerifier.sol      # Testnet proof verifier
│   │   │   ├── DecisionAuditLog.sol    # Immutable decision history
│   │   │   ├── CircuitBreaker.sol      # Emergency stop (3/5 multisig)
│   │   │   └── DynamicFeeContract.sol  # Example: AI-managed DeFi fee
│   │   ├── test/
│   │   └── script/Deploy.s.sol
│   │
│   ├── agents/             # Python multi-agent pipeline
│   │   └── living_contract/
│   │       ├── pipeline.py             # Main orchestrator loop
│   │       ├── config.py               # Settings (pydantic)
│   │       ├── agents/
│   │       │   ├── proposal_agent.py   # GPT-4o parameter proposals
│   │       │   └── executor.py         # On-chain tx submission
│   │       ├── feeds/price_feed.py     # Market data aggregation
│   │       └── provers/mock_prover.py  # ECDSA proof generator
│   │
│   ├── api/main.py         # FastAPI REST API
│   └── dashboard/          # Next.js real-time dashboard
│       └── src/app/page.tsx
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API Reference

```
GET  /health                          → health check
GET  /v1/contracts/latest-run         → latest agent decision
GET  /v1/contracts/history?limit=20   → run history
GET  /v1/contracts/policy             → policy boundaries
GET  /v1/contracts/stats              → aggregate statistics
POST /v1/contracts/trigger            → manually trigger agent cycle
```

Full docs: http://localhost:8000/docs

---

## Security Model

| Threat | Mitigation |
|---|---|
| AI proposes out-of-boundary value | On-chain boundary check — cannot bypass |
| Data poisoning | Multi-source price aggregation + quality score |
| Rogue agent | AGENT_ROLE required + ZK proof verification |
| Emergency | CircuitBreaker — 3/5 multisig to resume |
| Key compromise | Scoped session keys (EIP-7702 in prod) |

---

## Roadmap

- [x] **Phase 1** (MVP): Core contracts + agent pipeline + dashboard
- [ ] **Phase 2**: Real EZKL Groth16 ZK proof integration
- [ ] **Phase 3**: Mainnet deployment (Arbitrum + Base) + security audit
- [ ] **Phase 4**: SDK npm/pip publish + Policy Template Marketplace

---

## License

MIT free for commercial use. See [LICENSE](LICENSE).

---

Built for [KSGC 2026](https://ksgc.global) — Korea's flagship global startup accelerator.
