/** Work types — same list as backend/shared/category_catalog.py */

export interface WorkCategory {
  id: string;
  label: string;
  description: string;
}

export const WORK_CATEGORIES: WorkCategory[] = [
  {
    id: "physical_product",
    label: "Physical product",
    description: "Hardware, equipment, or anything you can hold or ship.",
  },
  {
    id: "software_app",
    label: "Software or app",
    description: "Applications, platforms, integrations, or internal tools.",
  },
  {
    id: "service_process",
    label: "Service or process",
    description: "A workflow, offering, or repeatable way work gets done.",
  },
  {
    id: "content_documents",
    label: "Content or documents",
    description: "Reports, guides, marketing packs, or document bundles.",
  },
  {
    id: "customer_request",
    label: "Customer request",
    description: "Something a client or stakeholder asked for.",
  },
  {
    id: "upgrade_replacement",
    label: "Upgrade or replacement",
    description: "Swapping, modernizing, or retiring something that exists today.",
  },
  {
    id: "kit_bundle",
    label: "Kit or bundle",
    description: "Multiple items sold or delivered together.",
  },
  {
    id: "industrial_equipment",
    label: "Industrial equipment",
    description: "Plant gear — valves, pumps, sensors, motors, and similar.",
  },
  {
    id: "other",
    label: "Other",
    description: "Doesn't fit above — describe it in the job name.",
  },
];

/** @deprecated use WORK_CATEGORIES */
export const PRODUCT_CATEGORIES = WORK_CATEGORIES;

export function categoryLabel(id: string): string {
  return WORK_CATEGORIES.find((item) => item.id === id)?.label ?? id;
}
