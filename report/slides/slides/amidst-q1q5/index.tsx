import type { Page, SlideMeta } from '@open-slide/core';
import { Step, Steps } from '@open-slide/core';

type AnnotatedPage = Page & {
  slideId: string;
  transition: 'fade' | 'slide-left' | 'slide-up' | 'morph';
  notes: string;
};

const canvasStyle: React.CSSProperties = {
  width: '100%',
  height: '100%',
  background: '#0b1120',
  color: '#f8fafc',
  padding: '64px 80px',
  boxSizing: 'border-box',
  fontFamily: 'Inter, Noto Sans TC, system-ui, sans-serif',
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'space-between',
};

const badgeStyle: React.CSSProperties = {
  display: 'inline-block',
  padding: '6px 14px',
  borderRadius: 999,
  background: 'rgba(56, 189, 248, 0.16)',
  color: '#38bdf8',
  fontSize: 20,
  fontWeight: 600,
  letterSpacing: '0.04em',
};

const cardStyle: React.CSSProperties = {
  background: 'rgba(30, 41, 59, 0.78)',
  border: '1px solid rgba(148, 163, 184, 0.25)',
  borderRadius: 18,
  padding: '24px 28px',
};

const footerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  fontSize: 18,
  color: '#94a3b8',
  borderTop: '1px solid rgba(148, 163, 184, 0.2)',
  paddingTop: 14,
};

/* -------------------------------------------------------------------------- */
/* Slide 1: Problem & Motivation                                              */
/* -------------------------------------------------------------------------- */
const Slide01Problem: AnnotatedPage = () => (
  <div style={canvasStyle}>
    <div>
      <span style={badgeStyle}>AMIDST Q1–Q5 · MULTI-CAMERA TRACKING &amp; HANDOFF</span>
      <h1 style={{ fontSize: 64, margin: '24px 0 16px', lineHeight: 1.12 }}>
        Traceable Multi-Camera Tracking &amp; Decision Switching
      </h1>
      <p style={{ fontSize: 28, color: '#cbd5e1', maxWidth: 1380 }}>
        When a target leaves a camera field of view or enters a blind zone, operators need
        auditable camera handoffs — not unverified guesses.
      </p>
      <Steps>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24, marginTop: 36 }}>
          <Step index={1}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 26, color: '#38bdf8', marginTop: 0 }}>1. Cross-Camera Ambiguity</h3>
              <p style={{ fontSize: 22, color: '#e2e8f0' }}>
                Appearance-similar distractors, occlusions, and blind zones cause wrong-target locks
                and missed reappearances.
              </p>
            </div>
          </Step>
          <Step index={2}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 26, color: '#fbbf24', marginTop: 0 }}>2. Rule vs. Agent Trade-off</h3>
              <p style={{ fontSize: 22, color: '#e2e8f0' }}>
                Can LLM / VLM agents improve camera switching over deterministic rules under strict
                real-time latency constraints?
              </p>
            </div>
          </Step>
          <Step index={3}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 26, color: '#34d399', marginTop: 0 }}>3. Evidence-First Engineering</h3>
              <p style={{ fontSize: 22, color: '#e2e8f0' }}>
                Every decision binds to source frames, clocks, hashes, and explicit uncertainty —
                identity remains <strong>UNCONFIRMED</strong>.
              </p>
            </div>
          </Step>
        </div>
      </Steps>
    </div>
    <div style={footerStyle}>
      <span>Amidst Q1–Q5 Research Report (#734 / #730)</span>
      <span>Identity: UNCONFIRMED | Slide 1 / 8</span>
    </div>
  </div>
);
Slide01Problem.slideId = '01-problem-motivation';
Slide01Problem.transition = 'fade';
Slide01Problem.notes =
  'Introduce the core operational problem: multi-camera tracking across blind zones and look-alike distractors. Emphasize our engineering boundary: visual appearance matching only (identity is always UNCONFIRMED), with full provenance back to source footage.';

/* -------------------------------------------------------------------------- */
/* Slide 2: Q1-Q5 System Architecture & Provenance / GT Isolation             */
/* -------------------------------------------------------------------------- */
const Slide02Architecture: AnnotatedPage = () => (
  <div style={canvasStyle}>
    <div>
      <span style={badgeStyle}>SYSTEM ARCHITECTURE &amp; DATA GOVERNANCE</span>
      <h2 style={{ fontSize: 52, margin: '18px 0 24px' }}>
        Q1–Q5 Pipeline, Provenance Chain &amp; Strict GT Isolation
      </h2>
      <Steps>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16 }}>
          <Step index={1}>
            <div style={cardStyle}>
              <strong style={{ color: '#38bdf8', fontSize: 24 }}>Q1</strong>
              <p style={{ fontSize: 20 }}>Filter cameras by selected condition</p>
            </div>
          </Step>
          <Step index={2}>
            <div style={cardStyle}>
              <strong style={{ color: '#38bdf8', fontSize: 24 }}>Q2</strong>
              <p style={{ fontSize: 20 }}>Locate matching person in footage</p>
            </div>
          </Step>
          <Step index={3}>
            <div style={cardStyle}>
              <strong style={{ color: '#38bdf8', fontSize: 24 }}>Q3</strong>
              <p style={{ fontSize: 20 }}>Parse structured UI query criteria</p>
            </div>
          </Step>
          <Step index={4}>
            <div style={cardStyle}>
              <strong style={{ color: '#38bdf8', fontSize: 24 }}>Q4</strong>
              <p style={{ fontSize: 20 }}>Judge whether frame holds target</p>
            </div>
          </Step>
          <Step index={5}>
            <div style={cardStyle}>
              <strong style={{ color: '#38bdf8', fontSize: 24 }}>Q5</strong>
              <p style={{ fontSize: 20 }}>Decide camera switch on exit</p>
            </div>
          </Step>
        </div>
        <Step index={6}>
          <div style={{ ...cardStyle, marginTop: 28, borderColor: 'rgba(52, 211, 153, 0.45)' }}>
            <h3 style={{ fontSize: 24, color: '#34d399', margin: '0 0 10px' }}>
              Non-Negotiable Isolation &amp; Provenance Rules
            </h3>
            <ul style={{ fontSize: 21, lineHeight: 1.55, margin: 0 }}>
              <li>Ground Truth, renderer trajectories, visibility, and depth are strictly scoring-side only.</li>
              <li>Source observations, projections, inferences, <code>MISSING</code>, and <code>UNKNOWN</code> stay distinct.</li>
              <li>Frozen datapack MANIFEST SHA-256: <code>4eee05ba92ac954d...74bca881b98</code>.</li>
            </ul>
          </div>
        </Step>
      </Steps>
    </div>
    <div style={footerStyle}>
      <span>Baseline: r004 A4-1 (50s) &amp; B4-1 (42s) + E3 16 hard segments</span>
      <span>Identity: UNCONFIRMED | Slide 2 / 8</span>
    </div>
  </div>
);
Slide02Architecture.slideId = '02-architecture-provenance';
Slide02Architecture.transition = 'slide-left';
Slide02Architecture.notes =
  'Walk through Q1 through Q5 step by step. Highlight that Q3 parses structured UI conditions (not open natural language), and stress GT isolation: inference and ranking never touch GT trajectories, depth, or visibility.';

/* -------------------------------------------------------------------------- */
/* Slide 3: E3 & E5 Results (Exact Preserved Verdicts)                        */
/* -------------------------------------------------------------------------- */
const Slide03E3E5Results: AnnotatedPage = () => (
  <div style={canvasStyle}>
    <div>
      <span style={badgeStyle}>FROZEN EVALUATION RESULTS (UNCHANGED VERDICTS)</span>
      <h2 style={{ fontSize: 48, margin: '14px 0 18px' }}>
        E3 (Attached) &amp; E5 (Open Agent AO / AO-L vs. B1 Rule)
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1.35fr 1fr', gap: 28, alignItems: 'center' }}>
        <div style={{ background: '#ffffff', borderRadius: 16, padding: 14 }}>
          <img
            src="../../../figures/fig1_e3_e5_summary.svg"
            alt="E3 and E5 frozen evaluation summary chart"
            style={{ width: '100%', height: 'auto', display: 'block' }}
          />
        </div>
        <Steps>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Step index={1}>
              <div style={cardStyle}>
                <strong style={{ color: '#f87171', fontSize: 22 }}>E3 (Attached Integration): Not Supported</strong>
                <p style={{ fontSize: 19, margin: '6px 0 0', color: '#cbd5e1' }}>
                  Pre-registered hypothesis not supported on the 16 hard E3 segments.
                </p>
              </div>
            </Step>
            <Step index={2}>
              <div style={cardStyle}>
                <strong style={{ color: '#f87171', fontSize: 22 }}>E5 H8a &amp; H8b (AO offline, K=3): Not Supported</strong>
                <p style={{ fontSize: 19, margin: '6px 0 0', color: '#cbd5e1' }}>
                  Wrong-target +129.1s [55.2, 193.1]; blind-lock +65.5s [39.7, 91.3]; McNemar p=0.019 favors B1.
                </p>
              </div>
            </Step>
            <Step index={3}>
              <div style={cardStyle}>
                <strong style={{ color: '#fbbf24', fontSize: 22 }}>E5 H8c (Top-1 Reappearance): Inconclusive</strong>
                <p style={{ fontSize: 19, margin: '6px 0 0', color: '#cbd5e1' }}>
                  AO 34/111 (0.306) vs B1 11/37 (0.297), diff +0.009 [-0.157, +0.172] includes 0.
                </p>
              </div>
            </Step>
            <Step index={4}>
              <div style={cardStyle}>
                <strong style={{ color: '#f87171', fontSize: 22 }}>E5 H8d (AO-L simlive, K=1): Not Supported</strong>
                <p style={{ fontSize: 19, margin: '6px 0 0', color: '#cbd5e1' }}>
                  Correct rate diff -0.511 [-0.617, -0.420]; McNemar p=4.8e-7 favors B1 (0 vs 22).
                </p>
              </div>
            </Step>
          </div>
        </Steps>
      </div>
    </div>
    <div style={footerStyle}>
      <span>Source: docs/operations/E5_REPORT_20261123.md (verdicts preserved verbatim)</span>
      <span>Identity: UNCONFIRMED | Slide 3 / 8</span>
    </div>
  </div>
);
Slide03E3E5Results.slideId = '03-e3-e5-results';
Slide03E3E5Results.transition = 'slide-left';
Slide03E3E5Results.notes =
  'Present the exact pre-registered verdicts without altering wording: E3 is not supported; in E5, H8a (primary), H8b (blind lock), and H8d (AO-L simlive K=1) are all Not Supported, while H8c (top-1 reappearance) is Inconclusive. Scope applies strictly to this A-open design on the 16 E3 segments.';

/* -------------------------------------------------------------------------- */
/* Slide 4: Latency Bottleneck & AO-L Zero-Latency Diagnostic                 */
/* -------------------------------------------------------------------------- */
const Slide04LatencyDiagnostic: AnnotatedPage = () => (
  <div style={canvasStyle}>
    <div>
      <span style={badgeStyle}>LATENCY BOTTLENECK &amp; DIAGNOSTIC APPROXIMATION</span>
      <h2 style={{ fontSize: 48, margin: '14px 0 18px' }}>
        Why AO-L Dropped to 24.8%: 52.7% Expired Calls
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 28, alignItems: 'center' }}>
        <div style={{ background: '#ffffff', borderRadius: 16, padding: 14 }}>
          <img
            src="../../../figures/fig3_latency_breakdown.svg"
            alt="Latency breakdown and AO-L zero-latency diagnostic chart"
            style={{ width: '100%', height: 'auto', display: 'block' }}
          />
        </div>
        <Steps>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <Step index={1}>
              <div style={cardStyle}>
                <h3 style={{ fontSize: 23, color: '#fb923c', margin: '0 0 8px' }}>Observed SimLive Expiry</h3>
                <p style={{ fontSize: 20, margin: 0 }}>
                  AO-L median/p95 latency reached <strong>4,784 / 10,524 ms</strong>; 98 of 186 calls
                  (<strong>52.7%</strong>) arrived too late (EXPIRED), leaving 510.6s in LOST state.
                </p>
              </div>
            </Step>
            <Step index={2}>
              <div style={{ ...cardStyle, borderColor: 'rgba(45, 212, 191, 0.5)' }}>
                <h3 style={{ fontSize: 23, color: '#2dd4bf', margin: '0 0 8px' }}>
                  Zero-Latency Diagnostic (APPROXIMATION)
                </h3>
                <p style={{ fontSize: 19, margin: 0, color: '#cbd5e1' }}>
                  Re-scores existing AO-L responses at query time without re-simulating tracker
                  divergence. Clearly labeled <strong>approximation</strong>; final number is{' '}
                  <code>PLACEHOLDER (awaiting #732)</code>.
                </p>
              </div>
            </Step>
          </div>
        </Steps>
      </div>
    </div>
    <div style={footerStyle}>
      <span>Approximation only: tracker state divergence is not re-simulated</span>
      <span>Identity: UNCONFIRMED | Slide 4 / 8</span>
    </div>
  </div>
);
Slide04LatencyDiagnostic.slideId = '04-latency-diagnostic';
Slide04LatencyDiagnostic.transition = 'morph';
Slide04LatencyDiagnostic.notes =
  'Explain the AO-L simlive drop: 52.7% of calls expired because API round-trip latency (p50 4.8s, p95 10.5s) exceeded target motion windows. Emphasize that the zero-latency diagnostic is an approximation (re-scoring existing answers at query time without re-simulating tracker state) and is currently PLACEHOLDER awaiting #732.';

/* -------------------------------------------------------------------------- */
/* Slide 5: E7 Local Models & Hardware Constraints                            */
/* -------------------------------------------------------------------------- */
const Slide05E7LocalModels: AnnotatedPage = () => (
  <div style={canvasStyle}>
    <div>
      <span style={badgeStyle}>E7 EXPLORATORY BENCHMARK · PLACEHOLDER AWAITING #732</span>
      <h2 style={{ fontSize: 48, margin: '14px 0 18px' }}>
        Five-Way Comparison &amp; Local Model Hardware Constraints
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1.45fr 1fr', gap: 28, alignItems: 'center' }}>
        <div style={{ background: '#ffffff', borderRadius: 16, padding: 14 }}>
          <img
            src="../../../figures/fig2_five_way_comparison.svg"
            alt="Five-way comparison chart with E7 placeholder bars"
            style={{ width: '100%', height: 'auto', display: 'block' }}
          />
        </div>
        <Steps>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Step index={1}>
              <div style={cardStyle}>
                <h3 style={{ fontSize: 22, color: '#c084fc', margin: '0 0 8px' }}>E7 Local Candidates (PLACEHOLDER)</h3>
                <p style={{ fontSize: 19, margin: 0, color: '#cbd5e1' }}>
                  <code>laya</code> (text), <code>Qwen-VL</code>, and diffusion VLM slots are hatched
                  placeholders pending #732 unified analysis JSON.
                </p>
              </div>
            </Step>
            <Step index={2}>
              <div style={{ ...cardStyle, borderColor: 'rgba(251, 191, 36, 0.5)' }}>
                <h3 style={{ fontSize: 22, color: '#fbbf24', margin: '0 0 8px' }}>
                  Colab Pro Latency != Local Demo Latency
                </h3>
                <p style={{ fontSize: 19, margin: 0, color: '#cbd5e1' }}>
                  E7 runs on Colab Pro GPUs as an <strong>exploratory</strong> benchmark. Local demo
                  machines have stricter VRAM/thermal limits; Windows RTX 3060 is smoke-test only.
                </p>
              </div>
            </Step>
          </div>
        </Steps>
      </div>
    </div>
    <div style={footerStyle}>
      <span>All E7 metrics read from unified_analysis_v1 JSON (never hand-copied)</span>
      <span>Identity: UNCONFIRMED | Slide 5 / 8</span>
    </div>
  </div>
);
Slide05E7LocalModels.slideId = '05-e7-local-models';
Slide05E7LocalModels.transition = 'slide-left';
Slide05E7LocalModels.notes =
  'Show the five-way comparison chart (Script Answer, B1 Rule, API AO/AO-L, and local models laya, Qwen-VL, diffusion VLM). Explicitly state that E7 numbers are PLACEHOLDER awaiting #732, E7 is exploratory, and Colab Pro GPU latency does NOT equal local demo machine latency.';

/* -------------------------------------------------------------------------- */
/* Slide 6: E6 Pre-registered Follow-up                                       */
/* -------------------------------------------------------------------------- */
const Slide06E6Followup: AnnotatedPage = () => (
  <div style={canvasStyle}>
    <div>
      <span style={badgeStyle}>E6 PRE-REGISTERED FOLLOW-UP · PENDING #726 + #732</span>
      <h2 style={{ fontSize: 50, margin: '18px 0 24px' }}>
        E6 Design: De-Anchoring, History &amp; Summary Context
      </h2>
      <Steps>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24 }}>
          <Step index={1}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 25, color: '#38bdf8', marginTop: 0 }}>De-Anchoring</h3>
              <p style={{ fontSize: 20, color: '#e2e8f0' }}>
                Reduce over-reliance on initial anchor boxes when the target exits or is occluded.
              </p>
            </div>
          </Step>
          <Step index={2}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 25, color: '#38bdf8', marginTop: 0 }}>Structured History</h3>
              <p style={{ fontSize: 20, color: '#e2e8f0' }}>
                Provide bounded temporal history of recent camera observations without leaking GT.
              </p>
            </div>
          </Step>
          <Step index={3}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 25, color: '#38bdf8', marginTop: 0 }}>Compact Summary</h3>
              <p style={{ fontSize: 20, color: '#e2e8f0' }}>
                Keep prompt context tight to control token cost and tail latency on 12 E6 segments.
              </p>
            </div>
          </Step>
        </div>
        <Step index={4}>
          <div style={{ ...cardStyle, marginTop: 28, borderColor: 'rgba(251, 191, 36, 0.5)' }}>
            <h3 style={{ fontSize: 24, color: '#fbbf24', margin: '0 0 8px' }}>
              Verdict Status: PLACEHOLDER (PENDING_PR726_AND_RUN)
            </h3>
            <p style={{ fontSize: 20, margin: 0, color: '#e2e8f0' }}>
              Pre-registered E6 verdict, effective families, and skew-sensitivity flag will be
              populated verbatim from <code>unified_analysis_v1.e6_verdict</code> after PR #726
              merges and #732 completes on Mac.
            </p>
          </div>
        </Step>
      </Steps>
    </div>
    <div style={footerStyle}>
      <span>E6 cannot overwrite E3/E5 frozen verdicts</span>
      <span>Identity: UNCONFIRMED | Slide 6 / 8</span>
    </div>
  </div>
);
Slide06E6Followup.slideId = '06-e6-followup';
Slide06E6Followup.transition = 'slide-up';
Slide06E6Followup.notes =
  'Summarize the three E6 follow-up interventions: de-anchoring, structured history, and compact summary. Clarify that the E6 verdict is strictly PLACEHOLDER until PR #726 merges and #732 executes on Mac, and E6 results will never rewrite E3 or E5 conclusions.';

/* -------------------------------------------------------------------------- */
/* Slide 7: Live Demo Showcase                                                */
/* -------------------------------------------------------------------------- */
const Slide07LiveDemo: AnnotatedPage = () => (
  <div style={canvasStyle}>
    <div>
      <span style={badgeStyle}>LIVE WORKBENCH SHOWCASE</span>
      <h2 style={{ fontSize: 50, margin: '18px 0 24px' }}>
        Interactive Q1–Q5 Workbench (Ports 8785 / 8791)
      </h2>
      <Steps>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28 }}>
          <Step index={1}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 26, color: '#34d399', marginTop: 0 }}>Baseline Demo (:8785)</h3>
              <ul style={{ fontSize: 21, lineHeight: 1.6, color: '#e2e8f0' }}>
                <li>Pinned to frozen baseline commit via <code>local/demo-pin.json</code>.</li>
                <li>Replays r004 A4-1 (50s) &amp; B4-1 (42s) across graph v3 cameras.</li>
                <li>Every prediction links to source frame hash, timestamp, and camera ID.</li>
              </ul>
            </div>
          </Step>
          <Step index={2}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 26, color: '#38bdf8', marginTop: 0 }}>Agent / Comparison Workbench (:8791)</h3>
              <ul style={{ fontSize: 21, lineHeight: 1.6, color: '#e2e8f0' }}>
                <li>Side-by-side rule vs. agent decision inspection with opt-in toggle.</li>
                <li>Explicit UI badges for <code>UNCONFIRMED</code> identity and <code>UNKNOWN</code> clearance.</li>
                <li>No silent fallback: timeouts, expiries, and missing detections are surfaced directly.</li>
              </ul>
            </div>
          </Step>
        </div>
      </Steps>
    </div>
    <div style={footerStyle}>
      <span>frontend/workbench/ | Acceptance A + 347 E2E browser checks passed</span>
      <span>Identity: UNCONFIRMED | Slide 7 / 8</span>
    </div>
  </div>
);
Slide07LiveDemo.slideId = '07-live-demo';
Slide07LiveDemo.transition = 'slide-left';
Slide07LiveDemo.notes =
  'Transition into the live demo on port 8785 (pinned baseline) and port 8791 (workbench comparison view). Point out the evidence drawer showing frame provenance and the persistent UNCONFIRMED identity badge.';

/* -------------------------------------------------------------------------- */
/* Slide 8: Limitations, Reproducibility & Future Work                        */
/* -------------------------------------------------------------------------- */
const Slide08LimitationsFuture: AnnotatedPage = () => (
  <div style={canvasStyle}>
    <div>
      <span style={badgeStyle}>LIMITATIONS, REPRODUCIBILITY &amp; NEXT STEPS</span>
      <h2 style={{ fontSize: 50, margin: '18px 0 24px' }}>
        Honest Boundaries &amp; Reproducible Research Artifacts
      </h2>
      <Steps>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28 }}>
          <Step index={1}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 25, color: '#f87171', marginTop: 0 }}>Key Limitations</h3>
              <ul style={{ fontSize: 20, lineHeight: 1.6, color: '#e2e8f0' }}>
                <li>Synthetic Blender footage only; real-world lighting &amp; crowding untested.</li>
                <li>Appearance matching only — identity is always <code>UNCONFIRMED</code>.</li>
                <li>Structured UI query (Q3); free-form NL prototype paused.</li>
                <li>E7 Colab Pro GPU latency cannot be equated to local demo latency.</li>
              </ul>
            </div>
          </Step>
          <Step index={2}>
            <div style={cardStyle}>
              <h3 style={{ fontSize: 25, color: '#34d399', marginTop: 0 }}>Reproducibility &amp; Future Work</h3>
              <ul style={{ fontSize: 20, lineHeight: 1.6, color: '#e2e8f0' }}>
                <li>Single <code>unified_analysis_v1</code> JSON drives slides, A0 poster, and paper (#659).</li>
                <li>Pre-registered protocols, frozen scorer SHA-256, and CI figure checks.</li>
                <li>Next: complete #732 (E6 + E7), integrate wall geometry, and test real footage.</li>
              </ul>
            </div>
          </Step>
        </div>
      </Steps>
    </div>
    <div style={footerStyle}>
      <span>Datapack MANIFEST SHA-256: 4eee05ba92ac954d4916f3000bd0d7c011297a75253ffe860605e74bca881b98</span>
      <span>Identity: UNCONFIRMED | Slide 8 / 8</span>
    </div>
  </div>
);
Slide08LimitationsFuture.slideId = '08-limitations-future';
Slide08LimitationsFuture.transition = 'fade';
Slide08LimitationsFuture.notes =
  'Close with clear research boundaries: synthetic scenes, UNCONFIRMED identity, structured UI queries, and Colab vs local demo hardware differences. Highlight our reproducible pipeline where one unified_analysis_v1 JSON updates slides, poster, and paper together.';

export const meta: SlideMeta = {
  title: 'Amidst Q1–Q5 Research Report',
  theme: 'dark',
  transition: 'slide-left',
};

export const slides: AnnotatedPage[] = [
  Slide01Problem,
  Slide02Architecture,
  Slide03E3E5Results,
  Slide04LatencyDiagnostic,
  Slide05E7LocalModels,
  Slide06E6Followup,
  Slide07LiveDemo,
  Slide08LimitationsFuture,
];

export const speakerNotes: Record<string, string> = Object.fromEntries(
  slides.map((slide) => [slide.slideId, slide.notes]),
);

export default slides satisfies Page[];
