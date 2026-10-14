# RANGER-IoT Formal Verification

This directory contains the Tamarin models introduced after the
STEP 7D.0 audit established that no formal model previously existed.

## STEP 7D.1 scope

`ranger_authorization_transport.spthy` is the first executable
security model.

It formalizes the authorization/transport boundary already present in
the implementation:

- LKH supplies authorization for protected rekey material.
- RANGER transports an opaque protected rekey capsule.
- authorized members may accept the new epoch;
- revoked members may observe or relay traffic but cannot accept;
- recovery is same-epoch;
- recovery requesters and helpers are authorized;
- the network is controlled by a Dolev-Yao adversary;
- authorized-member and Group-Manager compromise are explicit.

## Deliberate abstraction

The STEP 7D.1 theory does **not** claim to be a complete formal model
of the binary LKH tree.

The post-revocation authorization boundary is abstracted by a survivor
wrapping secret shared by the surviving authorized set.

The following are outside STEP 7D.1:

- exact binary-tree LKH update generation;
- exact LKH ciphertext coverage/minimality;
- sequential multi-epoch replay ordering;
- Reed-Solomon algebra;
- radio loss;
- topology;
- formal Python/C/Cooja equivalence;
- post-compromise security.

Those omissions are explicit publication guardrails.

A successful STEP 7D.1 therefore permits only a statement such as:

> The abstract authorization/transport model was machine-checked in
> Tamarin under the stated symbolic assumptions.

It does **not** permit:

> RANGER-IoT is formally verified.

The latter requires subsequent semantic refinement.
