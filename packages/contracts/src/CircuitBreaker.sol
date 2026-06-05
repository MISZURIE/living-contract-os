// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title CircuitBreaker
 * @notice Emergency stop mechanism. When tripped, all AI-driven updates halt.
 *         Requires multisig (3/5) to resume. Inspired by DeFi battle-tested patterns.
 */
contract CircuitBreaker {
    bool public isTripped;
    address public owner;

    // Multisig: 3 of 5 required to resume after trip
    address[5] public guardians;
    mapping(address => bool) public resumeVotes;
    uint256 public resumeVoteCount;
    uint256 public constant REQUIRED_VOTES = 3;

    event CircuitTripped(address indexed triggeredBy, string reason, uint256 timestamp);
    event CircuitResumed(uint256 timestamp);
    event GuardianVoted(address indexed guardian);

    error NotAuthorized();
    error AlreadyVoted();
    error NotTripped();

    constructor(address[5] memory _guardians) {
        owner = msg.sender;
        guardians = _guardians;
    }

    modifier onlyOwnerOrGuardian() {
        bool isGuardian = false;
        for (uint i = 0; i < 5; i++) {
            if (guardians[i] == msg.sender) { isGuardian = true; break; }
        }
        if (msg.sender != owner && !isGuardian) revert NotAuthorized();
        _;
    }

    function trip(string calldata reason) external onlyOwnerOrGuardian {
        isTripped = true;
        // Reset votes
        for (uint i = 0; i < 5; i++) {
            resumeVotes[guardians[i]] = false;
        }
        resumeVoteCount = 0;
        emit CircuitTripped(msg.sender, reason, block.timestamp);
    }

    function voteResume() external {
        if (!isTripped) revert NotTripped();
        bool isGuardian = false;
        for (uint i = 0; i < 5; i++) {
            if (guardians[i] == msg.sender) { isGuardian = true; break; }
        }
        if (!isGuardian) revert NotAuthorized();
        if (resumeVotes[msg.sender]) revert AlreadyVoted();

        resumeVotes[msg.sender] = true;
        resumeVoteCount++;

        emit GuardianVoted(msg.sender);

        if (resumeVoteCount >= REQUIRED_VOTES) {
            isTripped = false;
            emit CircuitResumed(block.timestamp);
        }
    }
}
