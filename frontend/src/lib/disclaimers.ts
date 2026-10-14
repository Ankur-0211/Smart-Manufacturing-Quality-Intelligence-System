/**
 * Mandatory permanent texts (roadmap 1.7, quoted from the project plan).
 * They must never be removed or paraphrased in the UI.
 */
export const DISCLAIMER_SIMULATION =
  'This system performs a software-level process simulation. It advances a virtual batch through a modelled sequence of manufacturing stages and evaluates each stage using rules and machine-learning models fitted to process data. It does not solve the physics of polymer melt flow, heat transfer, or shrinkage, and it does not compute material behaviour. Stage indicators are data-driven and rule-driven abstractions, not physical field solutions.'

export const DISCLAIMER_SHAP =
  'Attributions describe how this model reached its output for these inputs. They are statistical associations learned from historical data, not verified physical causes.'

export const DISCLAIMER_RECOMMENDATION =
  'These options reduce the FAILURE PROBABILITY ESTIMATED BY THIS MODEL for the given inputs. They are not validated process improvements. Applying them on a real machine requires a trial run and physical inspection.'

export const STATEMENT_SYNTHETIC_DATA =
  "The primary training corpus is synthetic. It is generated from documented process-engineering relationships and is intended to exercise and evaluate the system architecture. Model performance figures on synthetic data measure the system's ability to recover the generator's structure; they are not evidence of real-world accuracy."

export const MOCK_BANNER_TEXT = 'MOCK INTELLIGENCE — outputs are placeholders, not model predictions'
