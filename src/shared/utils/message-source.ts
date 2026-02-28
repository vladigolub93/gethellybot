export function isHardSystemSource(source: string): boolean {
  const normalized = source.trim().toLowerCase();
  return (
    normalized.startsWith("system_") ||
    normalized.startsWith("state_router.system") ||
    normalized.startsWith("state_router.control") ||
    normalized.startsWith("state_router.keyboard") ||
    normalized.startsWith("state_router.progress")
  );
}

