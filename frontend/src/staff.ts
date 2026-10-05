import type { AgentName } from "./api";

// Each agent is a member of the shop staff with a badge. The boss is the manager.
export interface StaffMember {
  name: AgentName;
  title: string;
  desk: string;
  initials: string;
  color: string; // department color (CSS var)
}

export const STAFF: Record<AgentName, StaffMember> = {
  boss: { name: "boss", title: "Boss", desk: "Store manager", initials: "B", color: "var(--boss)" },
  inventory: { name: "inventory", title: "Inventory", desk: "Stockroom", initials: "IN", color: "var(--inventory)" },
  accounting: { name: "accounting", title: "Accounting", desk: "Back office ledger", initials: "AC", color: "var(--accounting)" },
  facilities: { name: "facilities", title: "Facilities", desk: "Lease & building", initials: "FA", color: "var(--facilities)" },
  customer_service: {
    name: "customer_service",
    title: "Customer service",
    desk: "Front counter",
    initials: "CS",
    color: "var(--customer-service)",
  },
};

export const SPECIALISTS: AgentName[] = ["inventory", "accounting", "facilities", "customer_service"];

// Plain-language names for ticket statuses from the database.
export const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  waiting_on_approval: "Waiting on you",
  resolved: "Resolved",
};

export const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price request",
};

export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

// MCP tool names, explained for the manager (exact names stay visible too).
export const TOOL_HINT: Record<string, string> = {
  list_open_tickets: "read the ticket queue",
  get_ticket: "pulled the ticket file",
  check_stock: "checked the shelves",
  list_vendors: "looked up vendors",
  get_cash_and_obligations: "checked cash & bills",
  get_pricing: "ran the price math",
  create_draft: "wrote a draft",
  request_payment: "asked you to approve a payment",
  ship_order: "shipped an order",
  update_ticket: "updated the ticket",
};
