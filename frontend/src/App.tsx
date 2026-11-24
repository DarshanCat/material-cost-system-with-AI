import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import './ui-compat.css';
import type { ModuleId, UserRole, SystemHealthData, PurchaseRequest } from './types';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { DashboardView } from './components/DashboardView';
import { MaterialMasterView } from './components/MaterialMasterView';
import { VendorMasterView } from './components/VendorMasterView';
import { P2PCycleView } from './components/P2PCycleView';
import { PurchaseOrdersView } from './components/PurchaseOrdersView';
import { PurchaseRequestsView } from './components/PurchaseRequestsView';
import { ItemRequestsView } from './components/ItemRequestsView';
import { ReferenceDataView } from './components/ReferenceDataView';
import { DiagnosticsView } from './components/DiagnosticsView';
import { GRNManagementView } from './components/GRNManagementView';
import { MaterialIssueView } from './components/MaterialIssueView';
import { ReturnToStoreView } from './components/ReturnToStoreView';
import { WasteDispositionView } from './components/WasteDispositionView';
import { ExcelImportView } from './components/ExcelImportView';
import { LiveInventoryDashboard } from './components/LiveInventoryDashboard';
import { OpeningBalanceView } from './components/OpeningBalanceView';
import { PhysicalAuditView } from './components/PhysicalAuditView';
import { HeatMasterView } from './components/HeatMasterView';
import { HeatLogManagementView } from './components/HeatLogManagementView';
import { MaterialAliasView } from './components/MaterialAliasView';
import { ReconciliationDashboard } from './components/ReconciliationDashboard';
import { HeatExcelImportView } from './components/HeatExcelImportView';
import { CostingDashboard } from './components/CostingDashboard';
import { RolesResponsibilitiesView } from './components/RolesResponsibilitiesView';
import { SignInModal } from './components/SignInModal';
import { IdentityGate } from './components/IdentityGate';
import { UserManagementView } from './components/UserManagementView';
import { ErrorBoundary } from './components/ErrorBoundary';
import {
  apiFetch,
  devLogin,
  fetchCurrentUser,
  getAuthStatus,
  hasAccessToken,
  loginWithCredentials,
  signOut,
  UNAUTHORIZED_EVENT,
} from './api/client';
import type { AuthUser } from './api/client';
import {
  clearIdentitySession,
  configureIdentity,
  fetchIdentityProfile,
  signOutIdentity,
} from './api/identityAuth';
import type { IdentityProfile } from './api/identityAuth';
import {
  canAccessModule,
  hasPermission,
  MODULE_REQUIRED_PERMISSIONS,
} from './auth/permissions';

interface AuthState {
  phase: 'checking' | 'ready' | 'unavailable' | 'signed-out';
  user: AuthUser | null;
  provider: string;
  loginAvailable: boolean;
  message?: string;
  /** Identity provider only: who is signed in, even when not yet allowed into the application. */
  identityProfile: IdentityProfile | null;
  microsoftEnabled: boolean;
}

/** Only an approved user with a role who has already replaced the temporary password gets into the application. */
function userFromProfile(profile: IdentityProfile | null): AuthUser | null {
  if (!profile || profile.status !== 'active' || !profile.role || profile.must_change_password) return null;
  return {
    user_id: profile.user_id,
    role: profile.role,
    department: profile.department,
    status: profile.status,
    must_change_password: false,
    display_name: profile.display_name,
  };
}

export const App: React.FC = () => {
  const [activeModule, setActiveModule] = useState<ModuleId>('dashboard');
  const [preselectedPRForPO, setPreselectedPRForPO] = useState<PurchaseRequest | null>(null);
  const [health, setHealth] = useState<SystemHealthData | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(false);
  const [showSignInModal, setShowSignInModal] = useState<boolean>(false);
  const [auth, setAuth] = useState<AuthState>({
    phase: 'checking',
    user: null,
    provider: 'none',
    loginAvailable: false,
    identityProfile: null,
    microsoftEnabled: false,
  });

  // Role and user id come strictly from verified identity, never defaulting to Admin
  const currentRole: UserRole | null = auth.user?.role ?? null;
  const currentUserId: string | null = auth.user?.user_id ?? null;

  const signInAs = useCallback(async (role: UserRole) => {
    try {
      const user = await devLogin(role);
      setAuth((prev) => ({
        ...prev,
        phase: 'ready',
        user,
        message: undefined,
      }));
      setActiveModule('dashboard');
    } catch (err: any) {
      const errMessage = err?.message || 'Authentication failed.';
      setAuth((prev) => ({
        ...prev,
        phase: 'signed-out',
        user: null,
        message: errMessage,
      }));
      throw err;
    }
  }, []);

  const signInWithCreds = useCallback(async (username: string, password: string) => {
    try {
      const user = await loginWithCredentials(username, password);
      setAuth((prev) => ({
        ...prev,
        phase: 'ready',
        user,
        message: undefined,
      }));
      setActiveModule('dashboard');
    } catch (err: any) {
      const errMessage = err?.message || 'Credential login is unavailable.';
      setAuth((prev) => ({
        ...prev,
        phase: 'signed-out',
        user: null,
        message: errMessage,
      }));
      throw err;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const authStatus = await getAuthStatus();
        if (cancelled) return;
        // Google Identity Platform: e-mail + password accounts created and approved by an administrator.
        if (authStatus.provider === 'identity') {
          configureIdentity(authStatus.identity_api_key ?? '');
          const profile = hasAccessToken() ? await fetchIdentityProfile() : null;
          if (cancelled) return;
          if (!profile) clearIdentitySession();
          setAuth({
            phase: 'ready',
            user: userFromProfile(profile),
            provider: 'identity',
            loginAvailable: true,
            identityProfile: profile,
            microsoftEnabled: Boolean(authStatus.microsoft_enabled),
          });
          return;
        }
        // Behind Google Identity-Aware Proxy there is no bearer token; the proxy supplies the identity.
        const viaProxy = authStatus.provider === 'iap';
        if (viaProxy || hasAccessToken()) {
          const existing = await fetchCurrentUser({ withoutToken: viaProxy });
          if (cancelled) return;
          if (existing) {
            setAuth({
              phase: 'ready',
              user: existing,
              provider: authStatus.provider,
              loginAvailable: authStatus.login_available,
              identityProfile: null,
              microsoftEnabled: false,
            });
            return;
          }
        }
        setAuth({
          phase: 'ready',
          user: null,
          provider: authStatus.provider,
          loginAvailable: authStatus.login_available,
          identityProfile: null,
          microsoftEnabled: false,
          message: viaProxy
            ? 'Your Google account is signed in, but no role is assigned to it in this system. Ask the administrator to add it.'
            : undefined,
        });
      } catch {
        if (!cancelled) {
          setAuth({
            phase: 'ready',
            user: null,
            provider: 'none',
            loginAvailable: false,
            identityProfile: null,
            microsoftEnabled: false,
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      setAuth((prev) => {
        if (prev.provider === 'identity') {
          // The full-screen sign-in takes over; no modal and no half-signed-in state.
          clearIdentitySession();
          return { ...prev, phase: 'signed-out', user: null, identityProfile: null, message: 'Your session has expired. Please sign in again.' };
        }
        return { ...prev, phase: 'signed-out', user: null, message: 'Your session is missing or has expired. Please sign in again.' };
      });
      setShowSignInModal(true);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const fetchHealth = useCallback(async () => {
    setLoadingHealth(true);
    try {
      const response = await apiFetch('/api/v1/health');
      if (response.ok) {
        const data: SystemHealthData = await response.json();
        setHealth(data);
      } else {
        setHealth({
          status: 'degraded',
          app_name: 'VSPL Material Management & Costing System',
          environment: 'development',
          version: '0.2.1',
          costing_start_date: '2026-10-12',
          database: {
            connected: false,
            status: 'disconnected',
            message: `API responded with HTTP status ${response.status}`,
          },
          timestamp: new Date().toISOString(),
        });
      }
    } catch (err: any) {
      setHealth({
        status: 'degraded',
        app_name: 'VSPL Material Management & Costing System',
        environment: 'development',
        version: '0.2.0',
        costing_start_date: '2026-10-12',
        database: {
          connected: false,
          status: 'unreachable',
          message: 'Backend server is not reachable on port 8000',
        },
        timestamp: new Date().toISOString(),
      });
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  // When role changes or active module is unauthorized, auto-navigate to dashboard
  useEffect(() => {
    if (auth.user && !canAccessModule(auth.user.role, activeModule)) {
      setActiveModule('dashboard');
    }
  }, [auth.user?.role, activeModule]);

  const renderContent = () => {
    const isPublicModule = MODULE_REQUIRED_PERMISSIONS[activeModule] === null;

    if (!auth.user && !isPublicModule) {
      return (
        <div style={{ maxWidth: '520px', margin: '60px auto', textAlign: 'center', padding: '32px 24px', background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: '#fef3c7', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <span style={{ fontSize: '24px' }}>🔒</span>
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#0f172a', marginBottom: '8px' }}>
            Authentication Required
          </h2>
          <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '24px', lineHeight: 1.5 }}>
            You are not currently signed in. An authenticated user identity with appropriate role authorization is required to access the <strong>{activeModule}</strong> module.
          </p>
          <button
            type="button"
            className="erp-btn btn-primary"
            onClick={() => setShowSignInModal(true)}
            style={{ padding: '8px 20px', fontSize: '13px' }}
          >
            Sign In to Continue
          </button>
        </div>
      );
    }

    if (auth.user && !canAccessModule(auth.user.role, activeModule)) {
      return (
        <div style={{ maxWidth: '520px', margin: '60px auto', textAlign: 'center', padding: '32px 24px', background: '#fff', borderRadius: '12px', border: '1px solid #fecaca', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: '#fee2e2', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <span style={{ fontSize: '24px' }}>⛔</span>
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#991b1b', marginBottom: '8px' }}>
            Access Restricted
          </h2>
          <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '24px', lineHeight: 1.5 }}>
            Your current role (<strong>{auth.user.role}</strong>) does not have backend authorization to access the <strong>{activeModule}</strong> module.
          </p>
          <button
            type="button"
            className="erp-btn btn-secondary"
            onClick={() => setActiveModule('dashboard')}
            style={{ padding: '8px 20px', fontSize: '13px' }}
          >
            Return to Dashboard
          </button>
        </div>
      );
    }

    if (activeModule === 'dashboard') {
      return (
        <DashboardView
          health={health}
          loadingHealth={loadingHealth}
          onRefreshHealth={fetchHealth}
          currentRole={currentRole}
          onNavigate={(mod) => {
            if (canAccessModule(currentRole, mod)) {
              setActiveModule(mod);
            }
          }}
        />
      );
    }

    if (activeModule === 'system-health') {
      return (
        <DiagnosticsView
          health={health}
          loadingHealth={loadingHealth}
          onRefreshHealth={fetchHealth}
          canRunStrictDbCheck={hasPermission(currentRole, 'audit:read')}
        />
      );
    }

    if (!auth.user) {
      return null;
    }

    const activeRole = auth.user.role;
    const activeUserId = auth.user.user_id;

    switch (activeModule) {
      case 'heat-master':
        return (
          <HeatMasterView
            currentRole={activeRole}
            currentUserId={activeUserId}
            onNavigate={(mod) => setActiveModule(mod)}
          />
        );

      case 'material-master':
        return (
          <MaterialMasterView
            currentRole={activeRole}
            onRequestNewItem={() => setActiveModule('item-requests')}
          />
        );

      case 'vendor-master':
        return (
          <VendorMasterView
            currentRole={activeRole}
          />
        );

      case 'p2p-cycle':
        return (
          <P2PCycleView
            currentRole={activeRole}
            currentUserId={activeUserId}
            onNavigate={(mod, ctx) => {
              if (mod === 'purchase-orders' && ctx?.pr) {
                setPreselectedPRForPO(ctx.pr);
              }
              setActiveModule(mod);
            }}
          />
        );

      case 'purchase-requests':
        return (
          <PurchaseRequestsView
            currentRole={activeRole}
            currentUserId={activeUserId}
            onNavigateToPO={(pr) => {
              setPreselectedPRForPO(pr || null);
              setActiveModule('purchase-orders');
            }}
          />
        );

      case 'purchase-orders':
        return (
          <PurchaseOrdersView
            currentRole={activeRole}
            currentUserId={activeUserId}
            preselectedPR={preselectedPRForPO}
            onNavigateToPR={() => setActiveModule('purchase-requests')}
          />
        );

      case 'item-requests':
        return (
          <ItemRequestsView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'references':
        return <ReferenceDataView currentRole={activeRole} />;

      case 'grn-management':
        return (
          <GRNManagementView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'material-issue':
        return (
          <MaterialIssueView
            currentRole={activeRole}
            currentUserId={activeUserId}
            onNavigate={(mod) => setActiveModule(mod as any)}
          />
        );

      case 'return-to-store':
        return (
          <ReturnToStoreView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'waste-disposition':
        return (
          <WasteDispositionView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'excel-import':
        return (
          <ExcelImportView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'inventory-ledger':
        return (
          <LiveInventoryDashboard
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'opening-balances':
        return (
          <OpeningBalanceView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'physical-audits':
        return (
          <PhysicalAuditView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'heat-log':
        return (
          <HeatLogManagementView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'material-aliases':
        return (
          <MaterialAliasView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'heat-reconciliation':
        return (
          <ReconciliationDashboard
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'heat-import':
        return (
          <HeatExcelImportView
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'costing':
        return (
          <CostingDashboard
            currentRole={activeRole}
            currentUserId={activeUserId}
          />
        );

      case 'roles-responsibilities':
        return (
          <RolesResponsibilitiesView
            currentRole={activeRole}
            onSwitchRole={(role) => { if (auth.provider !== 'identity') void signInAs(role); }}
          />
        );

      case 'users':
        return <UserManagementView currentRole={activeRole} currentUserId={activeUserId} />;

      default:
        return null;
    }
  };

  const handleSignOut = async () => {
    if (auth.provider === 'identity') await signOutIdentity();
    else await signOut();
    setAuth((prev) => ({
      ...prev,
      phase: 'signed-out',
      user: null,
      identityProfile: null,
      message: 'You have signed out.',
    }));
    setActiveModule('dashboard');
  };

  if (auth.phase === 'checking') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '14px' }}>
        Loading...
      </div>
    );
  }

  // Identity provider: nobody sees any part of the application until approved, with a role and a password of their own.
  if (auth.provider === 'identity' && !auth.user) {
    return (
      <IdentityGate
        profile={auth.identityProfile}
        microsoftEnabled={auth.microsoftEnabled}
        notice={auth.message}
        onProfile={(profile) => {
          setAuth((prev) => ({
            ...prev,
            phase: 'ready',
            identityProfile: profile,
            user: userFromProfile(profile),
            message: undefined,
          }));
          if (userFromProfile(profile)) setActiveModule('dashboard');
        }}
        onSignOut={handleSignOut}
      />
    );
  }

  return (
    <div className="app-container">
      <Header
        currentRole={currentRole}
        onRoleChange={(role) => { if (auth.provider !== 'identity') void signInAs(role); }}
        roleSelectorEnabled={auth.loginAvailable}
        signedInAs={auth.user?.user_id}
        health={health}
        loadingHealth={loadingHealth}
        onRefreshHealth={fetchHealth}
        onOpenSignInModal={() => setShowSignInModal(true)}
      />
      <div className="erp-body">
        <Sidebar
          activeModule={activeModule}
          onSelectModule={setActiveModule}
          currentRole={currentRole}
        />
        <main className="erp-content">
          <ErrorBoundary resetKey={activeModule}>{renderContent()}</ErrorBoundary>
        </main>
      </div>

      <SignInModal
        isOpen={showSignInModal}
        onClose={() => setShowSignInModal(false)}
        currentRole={currentRole}
        currentUserId={currentUserId}
        loginAvailable={auth.loginAvailable}
        authProvider={auth.provider}
        onSelectRole={async (role) => {
          await signInAs(role);
        }}
        onCredentialSignIn={async (username, password) => {
          await signInWithCreds(username, password);
        }}
        onSignOut={handleSignOut}
      />
    </div>
  );
};

export default App;
