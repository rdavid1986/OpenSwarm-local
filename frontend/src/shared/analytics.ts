// Legacy shim. Forwards to serviceClient so every existing trackEvent()
// call site routes through the cloud relay without churning ~50 call
// sites across the frontend. Deleted entirely when those call sites
// migrate (or sooner — both paths run cleanly).
//
// New code should import from '@/shared/serviceClient' directly.

export {
  trackEvent,
  getLastAction,
  getLastPage,
  getTimeSpent,
} from './serviceClient';
