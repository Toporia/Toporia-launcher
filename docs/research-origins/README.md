# Toporia research origins audit

Research snapshot: 27 October 2026.

- [Interactive world map and publication timeline](index.html): open in a browser. Country boundaries and reference data are embedded; D3 and TopoJSON load from jsDelivr, so the visualization requires an internet connection.
- [Source data (CSV)](research-sources.csv) for spreadsheets and [JSON](research-sources.json) for reuse.
- [Source PDF](../../Toporia-library-with-links.pdf), 21 pages, updated 27 October 2026. The latest front-page total is 115 implementations. Earlier pages are dated snapshots, not extra implementations.

The map and timeline are a documentation snapshot, not a live view of plugin discovery. Update the data, embedded visualization data and audit together when revising the research catalogue.

The catalogue says its tables come from `toporia/plugins/LIBRARY.md`. That file was used to recover clickable source links and feature associations. The front-page additions, Berryman reference, Adam preprint, Kraft report and unlinked Ma citation were also included. Each DOI is counted once even if many features cite it. A preprint and its journal version are combined. Software packages, ordinary engineering practice and Toporia's own geometry/export utilities do not receive invented publication dates or research locations. Future-work entries and unregistered annealing are excluded.

## How to read the figures

- Geography means author affiliations in the cited publication, not nationality, publisher headquarters, download-host country, or current employment.
- Map counts are distinct reference-country pairs. International collaborations count once in each listed country, so country totals exceed located source totals. A paper with two institutions in one country counts once there.
- 82 references are on the timeline. 53 have verified country assignments, one (Michell) uses explicitly labelled historical inference, and 28 remain geographically unresolved. This is a documented partial geographic audit; an unresolved country is not evidence of no research in that country.
- Timeline uses the catalogue's conventional journal/issue year, including 2011 for top88 and 2021 for TOuNN despite earlier online dates. Hoghøj-Traff uses journal year 2022, with its 2021 preprint noted. Kraft is 1988; Adam is ICLR 2015 with original 2014 affiliations checked. Berryman and Ma years are inherited from the PDF and remain bibliographically qualified.
- The linked Bendsøe-Sigmund book edition says copyright 2004 while the catalogue cites 2003. It is plotted at the cited year, with that discrepancy retained.
- Country boundaries come from `@d3-maps/atlas@1.0.0`, countries-110m. They are a modern basemap, not reconstructed historical borders. Country fills do not express global research productivity or a ranking of the whole field.

## Findings and citation issues

The verified subset is concentrated in the United States and Denmark. DTU is a recurring institutional thread in density methods, filtering, robustness, nonlinear response, educational codes and machining. US institutions contribute stress methods, multiresolution, projection, geometry representations, neural parameterisation and recent optimisation. China supplies MMC-related and RBF code references; Japan supplies the reaction-diffusion code; Australia supplies the historical Michell context, Challis level-set code and a TOBS collaboration. Other verified collaborations reach Belgium, Sweden, the Netherlands, Brazil, the UK, Norway, Hungary, Germany and Canada. These observations are limited to this catalogue and its verified subset.

The RBF code citation labelled Luo et al. links to Wei, Li, Li and Wang (2018). The ESO reference under hard-kill BESO is Zhou and Rozvany's critique, not a Huang-Xie originating method. The pattern-repetition reference links to a paper about inverse projection and void distribution. These are flagged for review, not silently corrected in the repository or PDF. Toporia's independent variants should not be interpreted as exact reproductions of all cited methods.

The earliest directly cited root is Michell (1904). Chaikin (1974) supports curve post-processing. The core computational lineage spans CONLIN (1986), MMA (1987), SLSQP (1988), SIMP (1989), the filtering/projection and educational-code expansion around 2001-2011, manufacturing and alternative representations in the 2010s, and neural fields and SiMPL in the 2020s. The figures do not claim these are the first inventions across all topology-optimisation literature.

## Reference-by-reference evidence

Each entry below records its link, connected Toporia features, geography status and caveats. Publisher affiliation blocks and original author manuscripts were preferred. Unresolved items were not assigned a country based on author names or other papers.

### 1904 — Michell: limits of structural economy

- Reference: [10.1080/14786440409463229](https://doi.org/10.1080/14786440409463229)
- Countries: AUS. Status: Historical inference.
- Institutions: Melbourne research context.
- Toporia features: Michell Cantilever.
- Evidence/qualification: Historical location inferred from Melbourne consultancy, not a formal university affiliation: https://adb.online.anu.edu.au/biography/michell-anthony-george-maldon-7567

### 1974 — Chaikin: curve smoothing

- Reference: [10.1016/0146-664X%2874%2990028-8](https://doi.org/10.1016/0146-664X%2874%2990028-8)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Smooth outline (SVG + DXF).
- Evidence/qualification: Affiliation unresolved

### 1986 — Fleury & Braibant: CONLIN

- Reference: [10.1002/nme.1620230307](https://doi.org/10.1002/nme.1620230307)
- Countries: USA, BEL. Status: Verified affiliations.
- Institutions: UCLA; University of Liege.
- Toporia features: CONLIN (convex linearisation).
- Evidence/qualification: Verified publisher affiliations; Fleury is listed at UCLA at publication

### 1987 — Svanberg: method of moving asymptotes

- Reference: [10.1002/nme.1620240207](https://doi.org/10.1002/nme.1620240207)
- Countries: SWE. Status: Verified affiliations.
- Institutions: KTH, Stockholm.
- Toporia features: Method of moving asymptotes; MMA (pyMOTO), GCMMA (pyMOTO); MMA (mmapy), GCMMA (mmapy); MMA, CCSAQ, SLSQP, augmented Lagrangian + L-BFGS (NLopt).
- Evidence/qualification: Verified publisher affiliation

### 1988 — Kraft: sequential quadratic programming

- Reference: [kraft](https://jacobwilliams.github.io/slsqp/proc/slsqp.html)
- Countries: DEU. Status: Verified affiliations.
- Institutions: DFVLR, Oberpfaffenhofen.
- Toporia features: SLSQP.
- Evidence/qualification: Original report 1988; software author history identifies DFVLR Oberpfaffenhofen.

### 1989 — First and second order convex approximation strategies in structural optimization

- Reference: [10.1007/BF01743804](https://doi.org/10.1007/BF01743804)
- Countries: USA. Status: Verified affiliations.
- Institutions: UCLA.
- Toporia features: CONLIN (convex linearisation).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 1989 — Optimal shape design as a material distribution problem

- Reference: [10.1007/BF01650949](https://doi.org/10.1007/BF01650949)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: Element densities; SIMP (power law).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 1991 — Conn, Gould & Toint: globally convergent augmented Lagrangian

- Reference: [10.1137/0728030](https://doi.org/10.1137/0728030)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: MMA, CCSAQ, SLSQP, augmented Lagrangian + L-BFGS (NLopt).
- Evidence/qualification: Publisher title verified; full historical affiliations unresolved

### 1991 — Zhou & Rozvany: COC algorithm

- Reference: [10.1016/0045-7825%2891%2990046-9](https://doi.org/10.1016/0045-7825%2891%2990046-9)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Optimality criteria, several constraints.
- Evidence/qualification: Affiliation not independently verified for this paper

### 1992 — Diaz & Kikuchi: eigenvalue optimization

- Reference: [10.1002/nme.1620350707](https://doi.org/10.1002/nme.1620350707)
- Countries: USA. Status: Verified affiliations.
- Institutions: Michigan State; University of Michigan.
- Toporia features: Fundamental frequency (maximise).
- Evidence/qualification: Verified publisher affiliations

### 1993 — Ma, Kikuchi & Hagiwara: dynamic compliance

- Reference: unlinked citation in PDF.
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Dynamic compliance.
- Evidence/qualification: PDF names a 1993 paper without a link; exact bibliographic identity and geography unresolved.

### 1997 — Sigmund: compliant mechanisms

- Reference: [10.1080/08905459708945415](https://doi.org/10.1080/08905459708945415)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Sensitivity filter; 2-D Q4 compliant mechanism (Toporia); Output displacement (maximise); Force Inverter.
- Evidence/qualification: Affiliation not independently verified for this paper

### 1998 — Duysinx & Bendsoe: stress constraints

- Reference: [10.1002/%28SICI%291097-0207%2819981230%2943:8%3C1453::AID-NME480%3E3.0.CO%3B2-2](https://doi.org/10.1002/%28SICI%291097-0207%2819981230%2943:8%3C1453::AID-NME480%3E3.0.CO%3B2-2)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: L-bracket.
- Evidence/qualification: Affiliation not independently verified for this paper

### 1998 — Numerical instabilities in topology optimization: A survey on procedures dealing with checkerboards, mesh-dependencies and local minima

- Reference: [10.1007/BF01214002](https://doi.org/10.1007/BF01214002)
- Countries: DNK, SWE. Status: Verified affiliations.
- Institutions: DTU; Linkoping University.
- Toporia features: Equal steps.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 1999 — Material interpolation schemes in topology optimization

- Reference: [10.1007/s004190050248](https://doi.org/10.1007/s004190050248)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: Hashin-Shtrikman (fixed-nu upper envelope).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2000 — Conn, Gould & Toint: Trust Region Methods

- Reference: [10.1137/1.9780898719857](https://doi.org/10.1137/1.9780898719857)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: trust-constr (SciPy).
- Evidence/qualification: Multi-author book; institutional origins unresolved

### 2000 — Maximization of eigenvalues using topology optimization

- Reference: [10.1007/s001580050130](https://doi.org/10.1007/s001580050130)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: 2-D Q4 with vibration (Toporia).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2000 — Stiffness design of geometrically nonlinear structures using topology optimization

- Reference: [10.1007/s001580050089](https://doi.org/10.1007/s001580050089)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: 2-D Q4, large deformation (Toporia); End compliance (non-linear); Nonlinear Cantilever.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2001 — A 99 line topology optimization code written in Matlab

- Reference: [10.1007/s001580050176](https://doi.org/10.1007/s001580050176)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: Element densities; Sensitivity filter; Optimality criteria; MBB Beam; Cantilever.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2001 — An alternative interpolation scheme for minimum compliance topology optimization

- Reference: [10.1007/s001580100129](https://doi.org/10.1007/s001580100129)
- Countries: SWE. Status: Verified affiliations.
- Institutions: KTH.
- Toporia features: RAMP (rational).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2001 — Bourdin: density filtering

- Reference: [10.1002/nme.116](https://doi.org/10.1002/nme.116)
- Countries: DNK, USA. Status: Verified affiliations.
- Institutions: DTU; NYU correspondence address.
- Toporia features: Density filter.
- Evidence/qualification: Both listed addresses retained: https://onlinelibrary.wiley.com/doi/10.1002/nme.116

### 2001 — Bruns & Tortorelli: nonlinear structures and mechanisms

- Reference: [10.1016/S0045-7825%2800%2900278-4](https://doi.org/10.1016/S0045-7825%2800%2900278-4)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Density filter.
- Evidence/qualification: Affiliation not independently verified for this paper

### 2001 — On the validity of ESO type methods in topology optimization

- Reference: [10.1007/s001580050170](https://doi.org/10.1007/s001580050170)
- Countries: USA, HUN. Status: Verified affiliations.
- Institutions: Altair Engineering; Budapest University of Technology and Economics.
- Toporia features: BESO (hard kill).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations. This is a critique of ESO by Zhou and Rozvany, not an original Huang-Xie BESO paper.

### 2002 — Svanberg: globally convergent MMA / CCSAQ

- Reference: [10.1137/S1052623499362822](https://doi.org/10.1137/S1052623499362822)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: MMA (pyMOTO), GCMMA (pyMOTO); MMA (mmapy), GCMMA (mmapy); MMA, CCSAQ, SLSQP, augmented Lagrangian + L-BFGS (NLopt).
- Evidence/qualification: Affiliation not independently verified for this paper

### 2003 — Bendsoe & Sigmund: Topology Optimization

- Reference: [10.1007/978-3-662-05086-6](https://doi.org/10.1007/978-3-662-05086-6)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Symmetry filter; Pattern repetition; Compliance.
- Evidence/qualification: Catalogue cites 2003; linked publisher edition is copyright 2004; edition/date ambiguity

### 2003 — Bourdin & Chambolle: phase-field design-dependent loads

- Reference: [10.1051/cocv:2002070](https://doi.org/10.1051/cocv:2002070)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Phase-field regularised compliance.
- Evidence/qualification: Geography unresolved; do not interpret DOI suffix 2002 as publication year

### 2004 — Guest, Prevost & Belytschko: projection functions

- Reference: [10.1002/nme.1064](https://doi.org/10.1002/nme.1064)
- Countries: USA. Status: Verified affiliations.
- Institutions: Princeton; Northwestern.
- Toporia features: Heaviside projection (fixed or volume-preserving threshold); Multiply by a factor.
- Evidence/qualification: Verified publisher affiliations

### 2004 — Ishii & Aomura: extrusion constraints

- Reference: [10.1299/jsmea.47.198](https://doi.org/10.1299/jsmea.47.198)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Extrusion (constant cross-section).
- Evidence/qualification: Affiliation not independently verified for this paper

### 2005 — A reevaluation of the SIMP method with filtering and an alternative formulation for solid–void topology optimization

- Reference: [10.1007/s00158-005-0537-x](https://doi.org/10.1007/s00158-005-0537-x)
- Countries: USA. Status: Verified affiliations.
- Institutions: UIUC; Beckman Institute, UIUC.
- Toporia features: SINH (shared-density variant).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2005 — Berryman: elastic Hashin-Shtrikman formulas

- Reference: [berryman](https://sepwww.stanford.edu/sep/berryman/PS/PHYS.pdf)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Hashin-Shtrikman upper envelope.
- Evidence/qualification: PDF update cites Berryman 2005; full bibliographic identity and paper-time affiliation remain unresolved.

### 2006 — Topology optimization of heat conduction problems using the finite volume method

- Reference: [10.1007/s00158-005-0584-3](https://doi.org/10.1007/s00158-005-0584-3)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: 2-D Q4 heat conduction (Toporia); 3-D H8 heat conduction (Toporia); Thermal compliance; Heat Sink.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2006 — Wang & Wang: RBF level set

- Reference: [10.1002/nme.1536](https://doi.org/10.1002/nme.1536)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: RBF level set.
- Evidence/qualification: Affiliation not independently verified for this paper

### 2007 — Huang & Xie: convergent BESO

- Reference: [10.1016/j.finel.2007.06.006](https://doi.org/10.1016/j.finel.2007.06.006)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: BESO (soft kill).
- Evidence/qualification: Affiliation not independently verified for this paper

### 2007 — Morphology-based black and white filters for topology optimization

- Reference: [10.1007/s00158-006-0087-x](https://doi.org/10.1007/s00158-006-0087-x)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: Morphology filter (erode / dilate / open / close); Routing radius filter; Feature size; Grey level (M_nd) over the run.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2007 — Topological design of freely vibrating continuum structures for maximum values of simple and multiple eigenfrequencies and frequency gaps

- Reference: [10.1007/s00158-007-0101-y](https://doi.org/10.1007/s00158-007-0101-y)
- Countries: DNK. Status: Verified affiliations.
- Institutions: Aalborg University.
- Toporia features: 2-D Q4 with vibration (Toporia); Fundamental frequency (maximise); Vibrating Beam.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2008 — Birgin & Martinez: augmented Lagrangian

- Reference: [10.1080/10556780701577730](https://doi.org/10.1080/10556780701577730)
- Countries: BRA. Status: Verified affiliations.
- Institutions: University of Sao Paulo; University of Campinas.
- Toporia features: MMA, CCSAQ, SLSQP, augmented Lagrangian + L-BFGS (NLopt).
- Evidence/qualification: Publisher affiliations checked: https://www.tandfonline.com/doi/abs/10.1080/10556780701577730

### 2009 — A simple and effective inverse projection scheme for void distribution control in topology optimization

- Reference: [10.1007/s00158-008-0332-6](https://doi.org/10.1007/s00158-008-0332-6)
- Countries: USA, BRA. Status: Verified affiliations.
- Institutions: Federal University of Goias; UIUC; University of Sao Paulo.
- Toporia features: Pattern repetition.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations. Linked title concerns inverse projection and void distribution; catalogue places it under pattern repetition.

### 2010 — A computational paradigm for multiresolution topology optimization (MTOP)

- Reference: [10.1007/s00158-009-0443-8](https://doi.org/10.1007/s00158-009-0443-8)
- Countries: USA. Status: Verified affiliations.
- Institutions: UIUC.
- Toporia features: 2-D Q4 multiresolution (nested grids).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2010 — A discrete level-set topology optimization code written in Matlab

- Reference: [10.1007/s00158-009-0430-0](https://doi.org/10.1007/s00158-009-0430-0)
- Countries: AUS. Status: Verified affiliations.
- Institutions: University of Queensland.
- Toporia features: Hamilton-Jacobi level set with circular-hole derivative.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2010 — Huang & Xie: evolutionary topology optimization

- Reference: [10.1002/9780470689486](https://doi.org/10.1002/9780470689486)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: BESO (soft kill); BESO (hard kill).
- Evidence/qualification: Affiliation not independently verified for this book

### 2010 — Stress-based topology optimization for continua

- Reference: [10.1007/s00158-009-0440-y](https://doi.org/10.1007/s00158-009-0440-y)
- Countries: USA. Status: Verified affiliations.
- Institutions: UIUC; Caterpillar, Champaign.
- Toporia features: Material volume; Peak von Mises stress; L-bracket.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2010 — Takezawa, Nishiwaki & Kitamura: phase-field optimization

- Reference: [10.1016/j.jcp.2009.12.017](https://doi.org/10.1016/j.jcp.2009.12.017)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Phase-field regularised compliance.
- Evidence/qualification: Geography unresolved; publication title and year verified

### 2011 — An explicit parameterization for casting constraints in gradient driven topology optimization

- Reference: [10.1007/s00158-011-0632-0](https://doi.org/10.1007/s00158-011-0632-0)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: Casting (no undercuts).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2011 — Efficient topology optimization in MATLAB using 88 lines of code

- Reference: [10.1007/s00158-010-0594-7](https://doi.org/10.1007/s00158-010-0594-7)
- Countries: DNK, BEL. Status: Verified affiliations.
- Institutions: DTU; KU Leuven.
- Toporia features: Density filter; PDE (Helmholtz) filter; Sensitivity filter; 2-D Q4 plane stress (Toporia); Optimality criteria; Method of moving asymptotes; Augmented Lagrangian (local constraints); MBB Beam.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2011 — Eliminating beta-continuation from Heaviside projection and density filter algorithms

- Reference: [10.1007/s00158-011-0676-1](https://doi.org/10.1007/s00158-011-0676-1)
- Countries: USA. Status: Verified affiliations.
- Institutions: Johns Hopkins.
- Toporia features: MBB Beam (Fixed Projection).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2011 — Lazarov & Sigmund: Helmholtz filtering

- Reference: [10.1002/nme.3072](https://doi.org/10.1002/nme.3072)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU, Lyngby.
- Toporia features: PDE (Helmholtz) filter; Anisotropic PDE (Helmholtz) filter.
- Evidence/qualification: Verified publisher affiliations

### 2011 — On projection methods, convergence and robust formulations in topology optimization

- Reference: [10.1007/s00158-010-0602-y](https://doi.org/10.1007/s00158-010-0602-y)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: Heaviside projection (fixed or volume-preserving threshold); Multiply by a factor; When the design settles; Feature size; MBB Beam (Robust).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2013 — Qian: B-spline design space

- Reference: [10.1016/j.cma.2013.06.001](https://doi.org/10.1016/j.cma.2013.06.001)
- Countries: USA. Status: Verified affiliations.
- Institutions: Illinois Institute of Technology, Chicago.
- Toporia features: B-spline field.
- Evidence/qualification: Author manuscript: https://cdm.me.wisc.edu/pub/BtopCMAME13.pdf

### 2014 — An efficient 3D topology optimization code written in Matlab

- Reference: [10.1007/s00158-014-1107-x](https://doi.org/10.1007/s00158-014-1107-x)
- Countries: USA. Status: Verified affiliations.
- Institutions: IUPUI.
- Toporia features: 3-D H8 bricks (Toporia); Cantilever 3D.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2014 — Guo, Zhang & Zhong: moving morphable components

- Reference: [10.1115/1.4027609](https://doi.org/10.1115/1.4027609)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Moving morphable components (constant or variable thickness).
- Evidence/qualification: Affiliation not independently verified for this paper

### 2014 — Wang et al.: nonlinear energy interpolation

- Reference: [10.1016/j.cma.2014.03.021](https://doi.org/10.1016/j.cma.2014.03.021)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: 2-D Q4, large deformation (Toporia); Nonlinear Cantilever.
- Evidence/qualification: Affiliation not independently verified for this paper

### 2015 — Benchmarking optimization solvers for structural topology optimization

- Reference: [10.1007/s00158-015-1250-z](https://doi.org/10.1007/s00158-015-1250-z)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: Threshold to black and white.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2015 — Biyikli & To: proportional topology optimization

- Reference: [10.1371/journal.pone.0145041](https://doi.org/10.1371/journal.pone.0145041)
- Countries: USA. Status: Verified affiliations.
- Institutions: University of Pittsburgh.
- Toporia features: Proportional topology optimisation.
- Evidence/qualification: Author manuscript: https://d-scholarship.pitt.edu/downloads/83e340be-0a16-41a8-937c-3f24cb03937d

### 2015 — Kingma & Ba: Adam

- Reference: [adam](https://arxiv.org/pdf/1412.6980v1)
- Countries: NLD, CAN. Status: Verified affiliations.
- Institutions: University of Amsterdam; University of Toronto.
- Toporia features: Adam.
- Evidence/qualification: Original 2014 preprint checked for historical affiliations; conference publication 2015. Later arXiv revision adds OpenAI.

### 2015 — Matlab code for a level set-based topology optimization method using a reaction diffusion equation

- Reference: [10.1007/s00158-014-1190-z](https://doi.org/10.1007/s00158-014-1190-z)
- Countries: JPN. Status: Verified affiliations.
- Institutions: Kyoto University.
- Toporia features: Reaction-diffusion level set.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2015 — Norato, Bell & Tortorelli: geometry projection

- Reference: [10.1016/j.cma.2015.05.005](https://doi.org/10.1016/j.cma.2015.05.005)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Geometry projection (2D/3D capsule bars).
- Evidence/qualification: Institutional record confirms publication; complete affiliations unresolved

### 2015 — Zhou et al.: minimum length-scale constraints

- Reference: [10.1016/j.cma.2015.05.003](https://doi.org/10.1016/j.cma.2015.05.003)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Geometric minimum feature length.
- Evidence/qualification: DTU record confirms publication; full paper affiliations not independently checked

### 2016 — A new topology optimization approach based on Moving Morphable Components (MMC) and the ersatz material model

- Reference: [10.1007/s00158-015-1372-3](https://doi.org/10.1007/s00158-015-1372-3)
- Countries: CHN. Status: Verified affiliations.
- Institutions: Dalian University of Technology.
- Toporia features: Moving morphable components (constant or variable thickness).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2016 — Langelaar: additive manufacturing constraints

- Reference: [10.1016/j.addma.2016.06.010](https://doi.org/10.1016/j.addma.2016.06.010)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: AM overhang filter.
- Evidence/qualification: Affiliation not independently verified for this paper

### 2016 — Topology optimization considering overhang constraints: Eliminating sacrificial support material in additive manufacturing through design

- Reference: [10.1007/s00158-016-1551-x](https://doi.org/10.1007/s00158-016-1551-x)
- Countries: USA. Status: Verified affiliations.
- Institutions: US Army Research Laboratory; Johns Hopkins.
- Toporia features: Gaynor–Guest self-support projection (2-D).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2017 — An additive manufacturing filter for topology optimization of print-ready designs

- Reference: [10.1007/s00158-016-1522-2](https://doi.org/10.1007/s00158-016-1522-2)
- Countries: NLD. Status: Verified affiliations.
- Institutions: TU Delft.
- Toporia features: AM overhang filter.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2017 — Multi-material topology optimization using ordered SIMP interpolation

- Reference: [10.1007/s00158-016-1513-3](https://doi.org/10.1007/s00158-016-1513-3)
- Countries: USA, CHN. Status: Verified affiliations.
- Institutions: Jilin University; University of Michigan.
- Toporia features: Ordered SIMP (multi-material).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2017 — Zhang et al.: moving morphable voids

- Reference: [10.1016/j.cma.2017.05.002](https://doi.org/10.1016/j.cma.2017.05.002)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Moving morphable voids (restricted 2D superellipses).
- Evidence/qualification: Affiliation not independently verified for this paper

### 2018 — An 88-line MATLAB code for the parameterized level set method based topology optimization using radial basis functions

- Reference: [10.1007/s00158-018-1904-8](https://doi.org/10.1007/s00158-018-1904-8)
- Countries: CHN. Status: Verified affiliations.
- Institutions: South China University of Technology; Guangdong University of Petrochemical Technology; HKUST.
- Toporia features: RBF level set.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations. Catalogue says Luo; linked publication is Wei, Li, Li and Wang (2018). Attribution mismatch.

### 2018 — Minimum length-scale constraints for parameterized implicit function based topology optimization

- Reference: [10.1007/s00158-017-1883-1](https://doi.org/10.1007/s00158-017-1883-1)
- Countries: GBR. Status: Verified affiliations.
- Institutions: University of Aberdeen.
- Toporia features: Geometric minimum feature length.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2018 — QR-patterns: artefacts in multiresolution topology optimization

- Reference: [10.1007/s00158-018-2048-6](https://doi.org/10.1007/s00158-018-2048-6)
- Countries: NLD. Status: Verified affiliations.
- Institutions: TU Delft.
- Toporia features: 2-D Q4 multiresolution (nested grids).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2018 — Sivapuram & Picelli: TOBS

- Reference: [10.1016/j.finel.2017.10.006](https://doi.org/10.1016/j.finel.2017.10.006)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: TOBS (integer LP).
- Evidence/qualification: Affiliation not independently verified for this paper

### 2020 — A MATLAB code for topology optimization using the geometry projection method

- Reference: [10.1007/s00158-020-02552-0](https://doi.org/10.1007/s00158-020-02552-0)
- Countries: USA. Status: Verified affiliations.
- Institutions: University of Connecticut.
- Toporia features: Geometry projection (2D/3D capsule bars).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2020 — A new generation 99 line Matlab code for compliance topology optimization and its extension to 3D

- Reference: [10.1007/s00158-020-02629-w](https://doi.org/10.1007/s00158-020-02629-w)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU.
- Toporia features: Heaviside projection (fixed or volume-preserving threshold).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2020 — Feppon, Allaire & Dapogny: null-space optimization

- Reference: [10.1051/cocv/2020015](https://doi.org/10.1051/cocv/2020015)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Null-space optimiser.
- Evidence/qualification: Publication confirmed; full affiliation set unresolved

### 2020 — Huang: floating projection

- Reference: [10.1016/j.engstruct.2020.110330](https://doi.org/10.1016/j.engstruct.2020.110330)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Floating projection (FPTO).
- Evidence/qualification: Affiliation not independently verified from a primary source

### 2020 — Subedi, Verma & Suresh: post-processing review

- Reference: [10.1115/1.4047429](https://doi.org/10.1115/1.4047429)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Smooth outline (SVG + DXF).
- Evidence/qualification: Publication confirmed; full affiliations not independently checked from a primary source

### 2020 — Topology optimization with local stress constraints: a stress aggregation-free approach

- Reference: [10.1007/s00158-020-02573-9](https://doi.org/10.1007/s00158-020-02573-9)
- Countries: USA, BRA. Status: Verified affiliations.
- Institutions: Georgia Tech; PUC-Rio.
- Toporia features: Local von Mises stress (augmented Lagrangian).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2021 — A 101-line MATLAB code for topology optimization using binary variables and integer programming

- Reference: [10.1007/s00158-020-02719-9](https://doi.org/10.1007/s00158-020-02719-9)
- Countries: USA, AUS, BRA. Status: Verified affiliations.
- Institutions: UC San Diego; University of Sao Paulo; RMIT.
- Toporia features: TOBS (integer LP).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2021 — An efficient 137-line MATLAB code for geometrically nonlinear topology optimization using bi-directional evolutionary structural optimization method

- Reference: [10.1007/s00158-020-02816-9](https://doi.org/10.1007/s00158-020-02816-9)
- Countries: CHN. Status: Verified affiliations.
- Institutions: Northwestern Polytechnical University.
- Toporia features: 2-D Q4, large deformation (Toporia).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2021 — Huang: smooth or binary floating projection

- Reference: [10.1016/j.advengsoft.2020.102942](https://doi.org/10.1016/j.advengsoft.2020.102942)
- Countries: unresolved. Status: Unresolved geography.
- Institutions: unresolved.
- Toporia features: Floating projection (FPTO).
- Evidence/qualification: Affiliation not independently verified for this paper

### 2021 — PolyDyna: a Matlab implementation for topology optimization of structures subjected to dynamic loads

- Reference: [10.1007/s00158-021-02859-6](https://doi.org/10.1007/s00158-021-02859-6)
- Countries: USA. Status: Verified affiliations.
- Institutions: Georgia Tech; University of Missouri.
- Toporia features: Dynamic compliance (harmonic load).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2021 — PolyStress: a Matlab implementation for local stress-constrained topology optimization using the augmented Lagrangian method

- Reference: [10.1007/s00158-020-02760-8](https://doi.org/10.1007/s00158-020-02760-8)
- Countries: USA. Status: Verified affiliations.
- Institutions: Georgia Tech; University of Missouri.
- Toporia features: Local von Mises stress (augmented Lagrangian); Augmented Lagrangian (local constraints); L-bracket (local stress).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2021 — TOuNN: Topology Optimization using Neural Networks

- Reference: [10.1007/s00158-020-02748-4](https://doi.org/10.1007/s00158-020-02748-4)
- Countries: USA. Status: Verified affiliations.
- Institutions: UW-Madison.
- Toporia features: Neural coordinate field (2D/3D); Adam (augmented Lagrangian).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2021 — Topology optimization with linearized buckling criteria in 250 lines of Matlab

- Reference: [10.1007/s00158-021-02854-x](https://doi.org/10.1007/s00158-021-02854-x)
- Countries: DNK, USA. Status: Verified affiliations.
- Institutions: DTU; Johns Hopkins.
- Toporia features: 2-D Q4 with buckling (Toporia); Buckling load factor; Column Buckling.
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

### 2022 — Hoghoj & Traff: machining filter

- Reference: [10.1016/j.cma.2021.114488](https://doi.org/10.1016/j.cma.2021.114488)
- Countries: DNK. Status: Verified affiliations.
- Institutions: DTU, Lyngby.
- Toporia features: PDE machining (axis directions).
- Evidence/qualification: Journal 2022; preprint 2021: https://arxiv.org/html/2102.12999

### 2025 — A simple introduction to the SiMPL method for density-based topology optimization

- Reference: [10.1007/s00158-025-04008-9](https://doi.org/10.1007/s00158-025-04008-9)
- Countries: USA, NOR. Status: Verified affiliations.
- Institutions: Brown University; LLNL; Simula Research Laboratory.
- Toporia features: Mirror descent (SiMPL).
- Evidence/qualification: Publisher affiliation block checked; country counts include all listed affiliations.

