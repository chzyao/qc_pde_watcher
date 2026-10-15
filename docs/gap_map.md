# Gaps in quantum algorithms for CFD PDEs

A systematic map of 700 papers (arXiv, through 2026-10), 201 of them CFD-facing, tagged
against 14 algorithm families, 15 PDE targets and 14 capability axes.

---

## 1. How this map was built, and what it can and cannot measure

**Corpus.** 28 keyword queries against the arXiv API across the algorithm vocabulary
(QLSA/HHL, QSVT, LCU/LCHS, Schrödingerisation, Carleman/Koopman, time-marching,
variational, quantum lattice Boltzmann, annealing, tensor networks, analog/CV, quantum
walk, amplitude estimation) and the application vocabulary (Navier–Stokes, Euler, Burgers,
advection–diffusion, Poisson, heat, wave, Boltzmann/Vlasov, MHD, turbulence, CFD) returned
1,189 unique records. Keyword co-occurrence of a quantum-method term with a
differential-equation term cut this to 711; a hand-checked exclusion list removed 11
clearly off-topic records (quantum chemistry, QED foundations, unrelated benchmarks),
leaving **700**. A paper is "CFD-facing" if its abstract names Navier–Stokes, Euler/
compressible flow, Burgers/model-nonlinear equations, advection–diffusion/transport,
Boltzmann/kinetic, or turbulence/Reynolds number: **201 papers**. Citation counts come from
Crossref title matching at >0.90 similarity; 363 of 700 matched, the remainder being
preprint-only, which is expected in a field where half the corpus (353 of 700, 50.4%)
appeared in the 22 months to 2026-10-14.

**The measurement.** Tags are assigned by controlled-vocabulary regular expressions over
title + abstract. This measures *what a paper advertises as its contribution*, not
everything it contains — a paper may discuss boundary conditions in §4 without saying so in
the abstract. Coverage percentages below are therefore **lower bounds**, and should be read
as "how often the field foregrounds this axis," which is the right quantity for a gap map:
it measures what the community currently treats as a headline-worthy contribution. Two
further caveats. The Koopman regex pulls in some classical control and tensor-network work
(Korda & Mezić 2016, the most-cited record at 1,087 citations, is a classical MPC paper);
this is deliberate, because quantum-inspired tensor-train solvers are the moving classical
baseline (gap G10), but it means the family counts are not purely quantum. And a
semantic-classification pass over the abstracts was started but abandoned after it consumed
this session's language-model budget, so the tags are lexical rather than read — treat
individual cells as approximate and the column marginals as robust.

---

## 2. The shape of the field

CFD-facing output grew from 41 papers in 2019–2023 to 160 in 2024–2026 (Jan–Oct), roughly
a fivefold increase. Within that, five families dominate: variational/QML (n=47), quantum
lattice Boltzmann (n=43), Carleman/Koopman embedding (n=37), QSVT/block-encoding (n=25)
and tensor networks (n=21). The foundational linear-solver lineage (HHL → Clader's
preconditioned QLSA → Berry → Childs–Liu–Ostrander → Krovi) and the nonlinear-embedding
lineage (Liu et al. 2020 dissipative nonlinear ODEs → Carleman-LBM) still carry most of the
citations, but almost none of the recent output.

![Capability coverage by algorithm family across the 201 CFD-facing papers. Cell numbers are paper counts, colour is the fraction of that family's papers foregrounding the axis. Columns are ordered by overall coverage, so the gap frontier is the right-hand side: state preparation, noise, geometry, preconditioning and solver coupling.](coverage_matrix.png)

The matrix shows a field that is deep on one axis and thin on the rest. Nonlinearity is
foregrounded by 45% of CFD-facing papers and by 70% of the Carleman family. Everything an
engineer needs to run a real case is in the right-hand columns: state preparation (7.0%),
complex geometry (2.5%), condition number and preconditioning (2.0%), coupling to a
classical solver (2.0%).

![Capability coverage in 2019–2023 versus 2024–2026. The axes that rose are the quantum-algorithmic ones — grid dimensionality, resource estimation, nonlinearity, hardware, noise, error analysis. The engineering axes — geometry, baselines, boundary conditions, readout, preconditioning, solver coupling, state preparation — were flat or fell as the field grew fivefold.](gap_trajectory.png)

The second figure is the more consequential one, and the split in it is clean. Six axes
rose between the two windows: 2D/3D extension (9.8% → 24.4%, +14.6pp), explicit resource
estimation (0% → 11.2%, from zero to 18 papers), nonlinearity handling (36.6% → 47.5%),
hardware execution (12.2% → 15.6%), noise and error mitigation (4.9% → 6.9%) and
error/convergence analysis (7.3% → 8.8%). Every one of those is an axis the *quantum*
side of the problem owns — bigger grids, better circuits, more honest gate counts, more
devices.

The eight that fell are, without exception, the axes a CFD practitioner would ask about
first: complex geometry (4.9% → 1.9%), classical-baseline comparison (14.6% → 13.1%),
boundary conditions (12.2% → 11.2%), readout (9.8% → 8.8%), long-time integration
(19.5% → 18.8%), preconditioning (2.4% → 1.9%), solver coupling (2.4% → 1.9%) and state
preparation (7.3% → 6.9%). Fivefold growth bought progress on the quantum-algorithmic
axes and none at all on the engineering ones.

---

## 3. The unresolved contradiction at the centre of the field

Between September 2025 and August 2026 the field produced, in quick succession, four honest
end-to-end accountings and one full-stack advantage claim, and nobody has reconciled them.

- **arXiv:2603.12161** — *Quantum lower bounds for simulating fluid dynamics* gives evidence
  that quantum computers cannot significantly outperform classical fluid simulation in
  general: any algorithm simulating KdV for time *T* needs Ω(*T*²) copies of the initial
  state, and the incompressible Euler equations need e^Ω(*T*) in the worst case, proved via
  soliton divergence and instability-enabled state discrimination.
- **arXiv:2512.03758** — an end-to-end Carleman-LBM algorithm with full gate counts finds
  only that "a modest quantum advantage may be preserved for selected observables in the
  high-error-tolerance regime," bounding the scaling improvement over classical at
  O(Re^{3D/8}) and measuring numerically O(Re^1.936 × q_M) in 2D, with a data-extraction
  overhead q_M = O(Re^{3/8}) for drag alone.
- **arXiv:2608.21647** — *Measurement and reload costs* budgets shots and gates for a
  nonlinear wave solver in one cost-and-error model and finds the quantum cost per step
  (depth × shots) *exceeds* the classical cost as the grid grows, naming a "coherent,
  measurement-free nonlinear update" as the quantitative target any advantage must meet.
- **arXiv:2602.04239** — the only cross-paradigm benchmark on a common problem (1D Burgers,
  N = 4–128) concludes quantum methods yield no computational advantage over classical
  solvers absent fault tolerance, with a quantum tensor-network solver beating both the
  hydrodynamic Schrödinger equation and PINNs.
- Against these, **arXiv:2509.08807** claims a full-stack pathway with end-to-end
  exponential speedup for Navier–Stokes via spectral input/output and symmetry-based circuit
  synthesis, costing a 2^80-grid solve at 8.71M physical qubits and 42.6 days.

These cannot all be right about the same problem. The discrepancy is not mysterious — it
lives in what counts as the problem (final state vs. a scalar functional), what the initial
state costs, and whether the spectral I/O construction evades the Ω bounds or implicitly
restricts the admissible input class. But **no paper in the corpus audits one of these
claims against another under a shared cost model.** This is the single highest-leverage
opening in the field, and it is a theory-plus-accounting contribution rather than a new
algorithm.

---

## 4. Ranked gaps

Each gap gives the evidence from the corpus, what exists, what is missing, and an entry
point. "Coverage" is the percentage of the 201 CFD-facing papers foregrounding the axis.

### G1 — No common end-to-end cost model; advantage claims are not comparable
**Coverage:** resource estimates 9.0% (18 papers), of which perhaps five are genuinely
end-to-end. **Exists:** 2512.03758, 2511.18802, 2508.05346, 2608.15827, 2504.13033,
2509.08807. **Missing:** a shared accounting protocol — state preparation, Carleman
truncation, time-step count, κ-dependence, shot count per requested functional, error
budget, and the classical reference implementation — that makes two papers' numbers
commensurable. Without it the field cannot tell a real advance from a different set of
assumptions. **Entry point:** an audit paper that re-derives three published advantage
claims in one framework, with the cost model released as code. High citation potential,
needs no hardware, and the corpus contains the primary sources to audit.

### G2 — Readout is costed per paper, never per engineering functional
**Coverage:** 9.0% (18 papers), flat since 2019. **Exists:** 2511.20017 compares real- and
Fourier-space readout and shows 2D Burgers solvable without linearisation; 2406.06323
assesses drag-force extraction specifically; 2601.10166 computes velocity-field statistics
on hardware; 2512.03758 isolates q_M as a multiplicative overhead. **Missing:** a
functional-indexed theory of extraction cost. CFD does not want the state vector; it wants
drag and lift coefficients, wall shear stress distributions, energy spectra E(k),
dissipation rate, Reynolds stresses, PDFs and structure functions. Each has a different
quantum estimation cost, and some — spectra, low-order moments — are natively cheap on an
amplitude-encoded state while others require effectively full tomography. **Entry point:**
build the table. For each standard CFD observable, give the measurement primitive,
query complexity in grid size and Re, and the shot count for engineering-grade error bars.
This is the piece every downstream resource estimate currently invents for itself.

### G3 — Everything is a periodic box; wall-bounded flow in real geometry is absent
**Coverage:** 2.5% (5 papers), and *declining* as a share. **Exists:** 2510.17978 is the
strongest result — explicit circuit constructions embedding arbitrary complex-shaped
obstacles with Dirichlet/Neumann/mixed conditions into difference operators, with Trotter
error analysis showing no asymptotic gate-count growth in the Dirichlet case, applied to
linearised Euler with background flow. 2605.28135 demonstrates obstacle flow via
Carleman-LBM circuits. **Missing:** everything else — immersed-boundary forcing,
body-fitted and curvilinear meshes, multiblock and unstructured discretisations, adaptive
refinement. The efficient block-encoding constructions the field relies on
(arXiv:2602.10589 periodic-diagonal sparse matrices, arXiv:2607.11596 moment-structured
periodic finite-difference operators) explicitly assume periodic, uniform, translation-invariant
structure, which is exactly what a wall destroys. Boundary conditions as a category sit at
11.2% but are overwhelmingly 1D Dirichlet/periodic: the corpus contains **no** treatment of
wall models, synthetic inflow turbulence, or non-reflecting outflow — the boundary
conditions that actually determine whether a CFD simulation is usable. **Entry point:**
this is the most natural fit for a group working with a high-order compact finite-difference
immersed-boundary solver. A block-encoding of an immersed-boundary-forced operator, with
honest sparsity and κ accounting versus the periodic case, would be the first quantitative
statement of what geometry costs in a quantum CFD solver.

### G4 — The condition number is the dominant cost driver and nobody is attacking it
**Coverage:** 2.0% (4 CFD-facing papers). **Exists:** Clader et al. 2013 (arXiv:1301.2340,
248 citations) introduced preconditioned QLSA and remains, thirteen years on, essentially
the only construction; 2008.13295 covers fast inversion and preconditioned solvers for
matrix functions. **Missing:** quantum preconditioners for the pressure Poisson equation.
In an incompressible solver the Poisson solve is the expensive kernel and κ grows with mesh
refinement, so every QLSA-based complexity that is linear in κ degrades precisely in the
regime where advantage is claimed. There is no quantum multigrid, no quantum analogue of
ILU or approximate inverse, and no analysis of how classical preconditioner structure
survives block-encoding. **Entry point:** a sparse approximate-inverse or multigrid-like
quantum preconditioner for the Poisson/Helmholtz operator, with κ measured as a function of
grid refinement. This is the highest-value narrow technical target in the map: it is
well-posed, it has a clear classical theory to borrow from, and it unblocks an entire
algorithm family.

### G5 — Hybrid loops have no round-trip budget
**Coverage:** 2.0% (4 papers). **Exists:** 2608.21647 provides the cost-and-error model and
the negative result; 2512.05241 proposes multifidelity bridging; 2603.18222 builds an
HHL-based quantum–classical Navier–Stokes solver; 2509.08807 solves the I/O problem by
spectral encoding. **Missing:** a theory of how many measure-and-reload round trips a hybrid
solver can afford before the quantum step stops paying. Almost every practical proposal is a
quantum kernel inside a classical time loop — a quantum Poisson solve inside a projection
method, a quantum collision operator inside a classical streaming step — and each boundary
crossing destroys the amplitude encoding. **Entry point:** derive the break-even round-trip
count for a projection-method solver as a function of grid size, Re and target accuracy, and
state the condition under which the quantum Poisson solve survives being called every time
step. This is the result that decides whether near-term hybrid CFD is a research direction
or a dead end, and it directly complements G4.

### G6 — Nonlinearity is solved only in the weakly nonlinear regime
**Coverage:** 45.5% — the field's most crowded axis, which is why the restriction matters.
**Exists:** Carleman convergence requires dissipation to dominate nonlinearity (R < 1),
confining rigorous results to low Reynolds number. 2510.00722 establishes well-posedness and
convergence for parabolic PDEs; 2605.23380 examines lowest-order Carleman for low-Re
long-term behaviour; arXiv:2405.12714 revisits Carleman without dissipation; 2310.17973
reaches "moderate" Reynolds number. A homotopy-analysis family has appeared very recently
(arXiv:2406.15821 HAM-Schrödingerisation, arXiv:2512.21033 quantum homotopy for flow
problems, arXiv:2604.18924 Lindbladian HAM, arXiv:2609.06357 variational
homotopy-perturbation, arXiv:2609.39170 Frozen–Oseen HAM with LCHS). **Missing:** any method with provable convergence at turbulent
Reynolds number, and any error-plus-resource analysis of the homotopy family comparable to
what Carleman received. The homotopy papers are mostly formulation papers without gate
counts or convergence radii. **Entry point:** the rigorous convergence-and-resource analysis
of quantum homotopy methods, benchmarked against Carleman at matched Re. The methods exist;
the analysis does not.

### G7 — Unitary evolution does not conserve what CFD needs conserved
**Coverage:** effectively 3 papers. **Exists:** 2606.03407 (structure-preserving quantum
method of lines with mixed boundary conditions), 2609.38129 (conservation-syndrome quantum
error correction for lattice-Boltzmann algorithms — using conservation laws as error
syndromes, which is an elegant idea), 2609.21153 (shock-capturing for the linear advection
operator). **Missing:** discrete conservation of mass, momentum and kinetic energy under
quantum time evolution; entropy-stable schemes; nonlinear limiters and artificial viscosity,
which are non-unitary and non-local by construction and therefore genuinely hard to embed.
Compressible flow as a whole sits at 12 papers corpus-wide. For turbulence, energy-conserving
discretisation is not a nicety — it is what keeps a long DNS stable. **Entry point:** ask
what the quantum analogue of an energy-conserving skew-symmetric discretisation is, and
whether conservation can be imposed as a symmetry of the block-encoding rather than repaired
after the fact. 2609.38129 suggests the syndrome framing is fertile and nearly unexplored.

### G8 — Loading a turbulent initial field is unsolved
**Coverage:** 7.0% (14 papers). **Exists:** 2605.00302 (data loading for Carleman-linearised
LBM), 2508.05346 (geometric encoding of turbulence), arXiv:2601.03885 (efficient upsampling
for tensor-network-encoded functions). **Missing:** preparation of a divergence-free random
field with a prescribed energy spectrum as a quantum state, at a cost that does not swamp
the solve. Classical CFD has synthetic-eddy and spectral-synthesis methods for exactly this;
the quantum field has no analogue, yet the lower bounds in 2603.12161 are *stated in copies
of the initial state*, which makes preparation cost structurally central rather than
peripheral. **Entry point:** a synthetic-turbulence state-preparation circuit with cost
scaling in the spectral bandwidth, which simultaneously supplies the missing input to every
resource estimate in G1.

### G9 — One benchmark, no reporting standard
**Coverage:** classical-baseline comparison 13.1%, and only 2602.04239 compares paradigms on
a common problem. **Missing:** an agreed benchmark suite — the quantum analogue of
Taylor–Green vortex, lid-driven cavity, flow past a cylinder at specified Re, turbulent
channel flow — with agreed metrics (L2 error versus grid refinement, cost per converged
observable, shots to engineering tolerance) and a requirement that the classical reference
be a competent solver rather than a naive finite-difference stencil. **Entry point:** define
and publish the suite with reference classical solutions and a results template. Low
technical novelty, high field-level influence, and it is the kind of contribution that gets
adopted and cited for a decade.

### G10 — The classical baseline is moving faster than the quantum one
**Coverage:** tensor-network/quantum-inspired n=21 and rising. **Evidence:** 2608.26995
reports the first end-to-end quantum-inspired compressible Navier–Stokes DNS entirely in
tensor-train format — including new TT division and square-root algorithms enabling
Sutherland's law — validated against the classical solver HiPSTAR on a transient turbulent
Taylor–Green vortex at Mach 0.8 and 0.1. 2506.05477 compresses, simulates and synthesises
turbulence with tensor trains; 2602.04239 finds the tensor-network solver reaches L2 ≈ 10⁻⁷
with near-constant runtime scaling, beating both quantum-adjacent alternatives and classical
spectral baselines. **The implication:** quantum-inspired methods are capturing the
compressibility advantage of low-rank representation *without a quantum computer*. Any
claim of quantum advantage in CFD must now clear the tensor-train bar, not the
finite-difference bar — and 13.1% of the field compares against any classical baseline at
all. **Entry point:** whatever algorithm you build, benchmark against a TT solver. Also
worth treating as an opportunity: TT formalism is the natural bridge between CFD
discretisations and quantum circuits (the 2609.39962 review makes this argument), so a
TT-to-circuit compilation result travels in both directions.

### G11 — The formulations where quantum actually fits are the least explored
**Coverage:** a handful of 2026 papers. **Exists:** 2601.15523 (provable quantum speedups
for reaction-rate estimation in high-dimensional Fokker–Planck dynamics), 2606.15985
(quantum-enhanced MCMC for Lagrangian tracer dispersion in turbulence), 2608.27028 and
2608.26268 (quantum-assisted PDE-based Bayesian inverse problems, bosonic Hermite–Galerkin
encodings for high-dimensional PDEs), 2607.13641 (particle image velocimetry), 2601.17801
(reinforcement-learning flow control). **The argument:** direct velocity-field simulation
fights quantum computing's structure — it needs the whole state out, and the lower bounds
bite. High-dimensional statistical formulations do the opposite. PDF/Fokker–Planck methods
for turbulent reacting flow live in a composition space whose dimension grows with the
number of species, giving genuine exponential classical cost; the quantity wanted is a
scalar expectation or a reaction rate, which is exactly what amplitude estimation delivers
cheaply; and the initial condition is often a simple product distribution rather than a
turbulent field. Bayesian inverse problems and data assimilation share this shape.
**Entry point:** this is the strategically contrarian direction in the map — fewer than ten
papers, a clean argument for why quantum fits, and almost no competition. If the goal is
influence rather than incremental improvement, G11 plus G2 is a coherent thesis programme:
reformulate the CFD question as high-dimensional statistical estimation, then cost the
readout honestly.

---

## 5. Summary table

| Gap | Axis coverage (CFD-facing) | Trend 2019–23 → 2024–26 | Tractability | Payoff |
|---|---|---|---|---|
| G1 Common end-to-end cost model | 9.0% resource estimates | 0% → 11.2% | High — theory + accounting | Very high |
| G2 Functional-indexed readout cost | 9.0% | 9.8% → 8.8% | High | Very high |
| G3 Geometry, walls, real BCs | 2.5% | 4.9% → 1.9% | Medium | Very high |
| G4 Quantum preconditioning | 2.0% | 2.4% → 1.9% | Medium–hard | Very high |
| G5 Hybrid round-trip budget | 2.0% | 2.4% → 1.9% | High | High |
| G6 Nonlinearity beyond weak regime | 45.5% | 36.6% → 47.5% | Hard | High |
| G7 Conservation / structure preservation | ~1.5% | — | Medium | High |
| G8 Turbulent state preparation | 7.0% | 7.3% → 6.9% | Medium | High |
| G9 Benchmark suite and reporting standard | 13.1% baselines | 14.6% → 13.1% | High | High (field-level) |
| G10 Tensor-train baseline | n=21 and rising | rising | — (constraint) | — |
| G11 High-dimensional statistical formulations | <5% | emerging | Medium | Very high |

---

## 6. Three candidate programmes

**A. The auditor.** G1 + G2 + G9. Build the shared cost model, re-derive the three competing
advantage claims inside it, publish the benchmark suite and the readout cost table. No
hardware, no new algorithm, maximum field-level leverage — and it positions you as the
person whose numbers everyone else has to use.

**B. The wall.** G3 + G4 + G5. Immersed-boundary block-encodings, a Poisson preconditioner
with measured κ-versus-refinement, and the round-trip budget for a projection-method hybrid.
This is the programme that maps directly onto an existing high-order incompressible solver
and onto wall-bounded flow, and it attacks the three axes that fell or stayed flat while the
field grew fivefold.

**C. The reformulation.** G11 + G2 + G8. Move the question from "simulate the velocity
field" to "estimate a high-dimensional statistical functional" — PDF/Fokker–Planck transport,
Lagrangian dispersion, Bayesian inversion — where the dimension is genuinely exponential,
the output is a scalar, and the lower bounds of 2603.12161 do not obviously apply. Highest
risk, least crowded, and the best fit to the stated goal of influential contributions rather
than incremental ones.

---

## 7. Files

Paths below are relative to `data/` in this repository.

- `quantum_pde_corpus_tagged.csv` — 700 papers with arXiv ID, date, authors, algorithm
  families, PDE targets, capability axes, Crossref citations, venue, DOI, abstract.
- `coverage_matrix_counts.csv`, `coverage_matrix_fraction.csv` — the matrix behind figure 1.
- `gap_scorecard.csv` — per-axis coverage in both time windows.

Every arXiv identifier cited in this report (42 in total) was read back from the saved
corpus and verified to resolve to the paper described. Coverage percentages quoted in the
text were re-read from `gap_scorecard.csv` after it was written.
