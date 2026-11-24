import React, { useState, useEffect } from 'react';
import { 
  Search, 
  RefreshCw, 
  Eye
} from 'lucide-react';
import type { StockBalance, StockLedgerEntry, UOMStockSummary, UserRole } from '../types';
import { apiFetch } from '../api/client';

interface LiveInventoryDashboardProps {
  currentRole: UserRole;
  currentUserId: string;
}

export const LiveInventoryDashboard: React.FC<LiveInventoryDashboardProps> = () => {
  const [balances, setBalances] = useState<StockBalance[]>([]);
  const [uomSummaries, setUomSummaries] = useState<UOMStockSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [asOfDate, setAsOfDate] = useState<string>('');
  const [selectedItemHistory, setSelectedItemHistory] = useState<StockLedgerEntry[] | null>(null);
  const [selectedItemName, setSelectedItemName] = useState<string>('');
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);

  const fetchBalances = async () => {
    setLoading(true);
    try {
      let url = '/api/v1/ledger/balances';
      const params = new URLSearchParams();
      if (asOfDate) params.append('as_of_date', asOfDate);
      if (params.toString()) url += `?${params.toString()}`;

      let summaryUrl = '/api/v1/ledger/summary-by-uom';
      if (params.toString()) summaryUrl += `?${params.toString()}`;

      const [res, sumRes] = await Promise.all([
        apiFetch(url),
        apiFetch(summaryUrl),
      ]);

      if (res.ok) {
        const data = await res.json();
        setBalances(Array.isArray(data) ? data : (data?.items || []));
      }

      if (sumRes.ok) {
        const sumData = await sumRes.json();
        setUomSummaries(Array.isArray(sumData) ? sumData : []);
      }
    } catch (err) {
      console.error('Error fetching stock balances:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBalances();
  }, [asOfDate]);

  const fetchItemHistory = async (itemId: number, itemName: string, itemCode: string) => {
    setHistoryLoading(true);
    setSelectedItemName(`${itemCode} - ${itemName}`);
    try {
      const res = await apiFetch(`/api/v1/ledger/entries?material_item_id=${itemId}&size=100`);
      if (res.ok) {
        const data = await res.json();
        setSelectedItemHistory(Array.isArray(data) ? data : (data?.items || []));
      }
    } catch (err) {
      console.error('Error fetching movement history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const filteredBalances = balances.filter(b => {
    const matchesStatus = statusFilter === 'ALL' || b.status === statusFilter;
    const matchesSearch = 
      b.item_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
      b.item_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      b.category.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="erp-view">
      <div className="view-header">
        <div>
          <h2>Live Inventory Ledger & Balances</h2>
          <p className="subtitle">
            Authoritative, real-time stock balances strictly derived from immutable append-only journal entries.
          </p>
        </div>
        <div className="header-actions">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">As of Date:</span>
            <input
              type="date"
              className="form-control text-xs"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
            />
            {asOfDate && (
              <button className="erp-btn btn-sm btn-secondary text-xs" onClick={() => setAsOfDate('')}>
                Clear
              </button>
            )}
          </div>
          <button className="erp-btn btn-secondary" onClick={fetchBalances}>
            <RefreshCw size={14} className="btn-icon" /> Refresh
          </button>
        </div>
      </div>

      {/* UOM-Segregated Stock Summary Banner */}
      {uomSummaries.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {uomSummaries.map((uom) => (
            <div
              key={uom.uom_code}
              className="bg-white p-3.5 rounded-lg border border-slate-200 shadow-sm flex flex-col justify-between"
            >
              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    {uom.uom_name}
                  </span>
                  <span className="badge badge-outline font-mono text-xs font-bold text-slate-700">
                    {uom.uom_code}
                  </span>
                </div>
                <div className="flex items-baseline gap-1.5 mt-0.5">
                  <span className="font-mono text-xl font-bold text-slate-900">
                    {Number(uom.total_quantity).toLocaleString(undefined, {
                      minimumFractionDigits: uom.decimal_precision,
                      maximumFractionDigits: uom.decimal_precision,
                    })}
                  </span>
                  <span className="text-xs font-semibold text-slate-500">{uom.uom_code}</span>
                </div>
              </div>
              <div className="text-xs text-slate-500 mt-2.5 pt-2 border-t border-slate-100 flex justify-between">
                <span>{uom.item_count} {uom.item_count === 1 ? 'item' : 'items'}</span>
                <span>{uom.movement_count} journal {uom.movement_count === 1 ? 'entry' : 'entries'}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="filter-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="Search by Item Code, Name, Category..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="filter-group">
          <span className="filter-label">Stock Status:</span>
          {['ALL', 'IN_STOCK', 'OUT_OF_STOCK', 'UNINITIALIZED', 'NEGATIVE_STOCK'].map((st) => (
            <button
              key={st}
              className={`filter-btn ${statusFilter === st ? 'active' : ''}`}
              onClick={() => setStatusFilter(st)}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Stock Balances Table */}
      <div className="erp-table-container">
        <table className="erp-table">
          <thead>
            <tr>
              <th>Item Code</th>
              <th>Material Name</th>
              <th>Category</th>
              <th>Department</th>
              <th>Derived Balance</th>
              <th>UOM</th>
              <th>Ledger Status</th>
              <th>Movements</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="text-center p-4">Deriving inventory balances from journal...</td></tr>
            ) : filteredBalances.length === 0 ? (
              <tr><td colSpan={9} className="text-center p-4">No material items match current criteria.</td></tr>
            ) : (
              filteredBalances.map((b) => (
                <tr key={b.material_item_id}>
                  <td className="font-mono font-bold text-slate-800">{b.item_code}</td>
                  <td className="font-medium">{b.item_name}</td>
                  <td>
                    <span className="badge badge-outline">{b.category}</span>
                  </td>
                  <td>{b.department_name || '—'}</td>
                  <td className="font-mono text-base font-semibold">
                    {b.status === 'UNINITIALIZED' ? (
                      <span className="text-slate-400 italic">Uninitialized</span>
                    ) : (
                      <span className={Number(b.current_balance) < 0 ? 'text-red-600' : 'text-slate-900'}>
                        {b.current_balance}
                      </span>
                    )}
                  </td>
                  <td className="font-mono text-xs">{b.uom_code}</td>
                  <td>
                    {b.status === 'IN_STOCK' && <span className="badge badge-success">In Stock</span>}
                    {b.status === 'OUT_OF_STOCK' && <span className="badge badge-secondary">Zero Balance</span>}
                    {b.status === 'UNINITIALIZED' && <span className="badge badge-warning">Uninitialized</span>}
                    {b.status === 'NEGATIVE_STOCK' && <span className="badge badge-danger">Negative Stock</span>}
                  </td>
                  <td className="text-xs text-slate-500">
                    {b.movement_count} journal {b.movement_count === 1 ? 'entry' : 'entries'}
                  </td>
                  <td>
                    <button
                      className="erp-btn btn-sm btn-outline"
                      onClick={() => fetchItemHistory(b.material_item_id, b.item_name, b.item_code)}
                    >
                      <Eye size={12} className="btn-icon" /> Ledger
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Item Movement History Drawer / Modal */}
      {selectedItemHistory && (
        <div className="modal-backdrop" onClick={() => setSelectedItemHistory(null)}>
          <div className="modal-content max-w-5xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Movement Journal: {selectedItemName}</h3>
              <button className="close-btn" onClick={() => setSelectedItemHistory(null)}>✕</button>
            </div>
            <div className="modal-body">
              {historyLoading ? (
                <div className="p-4 text-center">Loading ledger entries...</div>
              ) : selectedItemHistory.length === 0 ? (
                <div className="p-4 text-center text-slate-500">No journal entries recorded for this material.</div>
              ) : (
                <div className="erp-table-container max-h-96 overflow-y-auto">
                  <table className="erp-table text-xs">
                    <thead>
                      <tr>
                        <th>Entry #</th>
                        <th>Tx Date</th>
                        <th>Movement Type</th>
                        <th>Delta</th>
                        <th>UOM</th>
                        <th>Source Doc #</th>
                        <th>Type</th>
                        <th>Posted By</th>
                        <th>Reason / Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedItemHistory.map((e) => (
                        <tr key={e.id}>
                          <td className="font-mono font-medium">{e.entry_number}</td>
                          <td>{e.transaction_date}</td>
                          <td>
                            <span className="badge badge-outline">{e.movement_type}</span>
                          </td>
                          <td className="font-mono font-semibold">
                            <span className={Number(e.quantity_delta) > 0 ? 'text-emerald-700' : Number(e.quantity_delta) < 0 ? 'text-red-700' : 'text-slate-600'}>
                              {Number(e.quantity_delta) > 0 ? `+${e.quantity_delta}` : e.quantity_delta}
                            </span>
                          </td>
                          <td>{e.uom_code}</td>
                          <td className="font-mono font-medium">{e.source_document_number}</td>
                          <td><span className="badge">{e.source_document_type}</span></td>
                          <td>{e.posted_by}</td>
                          <td>{e.reason || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="erp-btn btn-secondary" onClick={() => setSelectedItemHistory(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
