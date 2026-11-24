/** Admin user-management API (backend `/api/v1/users`, permission `user:manage`). */

import type { UserRole } from '../types';
import { apiFetch, readApiError } from './client.ts';

export const ASSIGNABLE_ROLES: readonly UserRole[] = ['Stores', 'Foundry', 'Purchase', 'Management', 'Admin', 'Quality', 'Accounts'];

export type UserStatus = 'active' | 'pending' | 'rejected' | 'disabled';

export interface ManagedUser {
  id: number;
  email: string;
  display_name: string;
  role: UserRole | null;
  department: string;
  status: UserStatus;
  auth_source: string;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
  decided_by: string | null;
  decided_at: string | null;
}

export interface UserAuditEntry {
  id: number;
  user_email: string;
  action: string;
  actor: string;
  detail: string | null;
  created_at: string;
}

/** A user plus the one-time temporary password the server generated. The password is never retrievable again. */
export interface UserWithTempPassword {
  user: ManagedUser;
  temporary_password: string;
}

export interface CreateUserInput {
  email: string;
  display_name: string;
  role: UserRole;
  department?: string;
}

async function parse<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) throw new Error(await readApiError(res, fallback));
  return (await res.json()) as T;
}

function jsonInit(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}

/** Remove empty optional fields so the server applies its own defaults. */
function compact<T extends Record<string, unknown>>(input: T): Partial<T> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(input)) {
    if (v !== undefined && v !== null && !(typeof v === 'string' && v.trim() === '')) out[k] = typeof v === 'string' ? v.trim() : v;
  }
  return out as Partial<T>;
}

export async function listUsers(status?: UserStatus): Promise<{ items: ManagedUser[]; total: number }> {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return parse(await apiFetch(`/api/v1/users${query}`), 'Could not load users');
}

export async function createUser(input: CreateUserInput): Promise<UserWithTempPassword> {
  return parse(await apiFetch('/api/v1/users', jsonInit('POST', compact({ ...input }))), 'Could not create the user');
}

export async function approveUser(id: number, role: UserRole, department?: string): Promise<ManagedUser> {
  return parse(await apiFetch(`/api/v1/users/${id}/approve`, jsonInit('POST', compact({ role, department }))), 'Could not approve the user');
}

export async function rejectUser(id: number, reason?: string): Promise<ManagedUser> {
  return parse(await apiFetch(`/api/v1/users/${id}/reject`, jsonInit('POST', compact({ reason }))), 'Could not reject the user');
}

export async function updateUser(
  id: number,
  changes: { role?: UserRole; department?: string; display_name?: string },
): Promise<ManagedUser> {
  return parse(await apiFetch(`/api/v1/users/${id}`, jsonInit('PATCH', compact({ ...changes }))), 'Could not update the user');
}

export async function disableUser(id: number): Promise<ManagedUser> {
  return parse(await apiFetch(`/api/v1/users/${id}/disable`, jsonInit('POST')), 'Could not disable the user');
}

export async function enableUser(id: number): Promise<ManagedUser> {
  return parse(await apiFetch(`/api/v1/users/${id}/enable`, jsonInit('POST')), 'Could not enable the user');
}

export async function resetUserPassword(id: number): Promise<UserWithTempPassword> {
  return parse(await apiFetch(`/api/v1/users/${id}/reset-password`, jsonInit('POST')), 'Could not reset the password');
}

export async function listUserAuditLog(limit = 100): Promise<{ items: UserAuditEntry[] }> {
  return parse(await apiFetch(`/api/v1/users/audit-log?limit=${encodeURIComponent(String(limit))}`), 'Could not load the audit log');
}
