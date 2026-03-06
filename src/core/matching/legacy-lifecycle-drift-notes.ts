import {
  LEGACY_MATCH_STATUSES,
} from "./legacy-matching-compat";

/**
 * Legacy lifecycle drift notes (documentation-only).
 *
 * This file intentionally has no runtime wiring and no mutation helpers.
 * It exists to make cleanup intent explicit while legacy vocabulary is still persisted.
 */

/**
 * Deprecated legacy statuses:
 * - kept only for backward compatibility
 * - do not introduce into new writes or decision gates
 */
export const DEPRECATED_LEGACY_MATCH_STATUSES = [
  LEGACY_MATCH_STATUSES.CONTACT_PENDING,
  LEGACY_MATCH_STATUSES.CLOSED,
] as const;

/**
 * Overloaded legacy statuses:
 * - still active in runtime
 * - should not be expanded
 * - should eventually be replaced by explicit canonical lifecycle ownership
 */
export const OVERLOADED_LEGACY_MATCH_STATUSES = [
  LEGACY_MATCH_STATUSES.CANDIDATE_APPLIED,
] as const;

/**
 * Deprecated helper methods retained in storage layer.
 * Method names are strings here to keep this file read-only and non-invasive.
 */
export const DEPRECATED_LEGACY_HELPERS = [
  "MatchStorageService.setContactPending",
] as const;

/**
 * Canonical replacement direction (planning only):
 * - manager exposure ownership: `ManagerExposureService` + `MatchLifecycleService.sendToManager`
 * - canonical lifecycle vocabulary: `src/core/matching/match-statuses.ts`
 */
export const LEGACY_CLEANUP_REPLACEMENT_DIRECTION = {
  managerExposureOwner: "ManagerExposureService.exposeCandidateToManager",
  canonicalMatchLifecycleOwner: "MatchLifecycleService",
} as const;
