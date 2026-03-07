export type GatekeeperConfig = {
  minConfidence: number;
};

export const DEFAULT_GATEKEEPER_CONFIG: GatekeeperConfig = {
  minConfidence: 0.6,
};
