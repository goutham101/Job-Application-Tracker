export const STAGES = [
  { value: "applied", label: "Applied" },
  { value: "oa", label: "Online Assessment" },
  { value: "phone_screen", label: "Phone Screen" },
  { value: "interview", label: "Interview" },
  { value: "final_round", label: "Final Round" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
  { value: "withdrawn", label: "Withdrawn" },
];

export const STAGE_LABELS = Object.fromEntries(
  STAGES.map((s) => [s.value, s.label])
);

export const TERMINAL_STAGES = new Set(["offer", "rejected", "withdrawn"]);

// Compact labels for tight spots (chart transition labels).
export const STAGE_SHORT = {
  applied: "Applied",
  oa: "OA",
  phone_screen: "Phone",
  interview: "Interview",
  final_round: "Final",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const SOURCES = [
  { value: "cold_apply", label: "Cold apply" },
  { value: "referral", label: "Referral" },
  { value: "career_fair", label: "Career fair" },
  { value: "recruiter", label: "Recruiter" },
  { value: "other", label: "Other" },
];

export const SOURCE_LABELS = Object.fromEntries(
  SOURCES.map((s) => [s.value, s.label])
);

export const stageColor = (stage) => `var(--st-${stage})`;
