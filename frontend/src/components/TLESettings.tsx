/**
 * TLE Settings component for orbit configuration.
 *
 * Allows manual TLE input and fetching from CelesTrak.
 */

import { useState, useEffect } from 'react';

interface TLEData {
  line1: string;
  line2: string;
  inclination: number;
  period: number;
}

interface TLESettingsProps {
  isConnected: boolean;
}

// CelesTrak API for TLE search
const CELESTRAK_SEARCH_URL = 'https://celestrak.org/NORAD/elements/gp.php';

export function TLESettings({ isConnected }: TLESettingsProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [currentTLE, setCurrentTLE] = useState<TLEData | null>(null);
  const [line1, setLine1] = useState('');
  const [line2, setLine2] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('AE1C');

  // Fetch current TLE on mount
  useEffect(() => {
    if (isConnected) {
      fetchCurrentTLE();
    }
  }, [isConnected]);

  const fetchCurrentTLE = async () => {
    try {
      const response = await fetch('/api/simulation/tle');
      if (response.ok) {
        const data = await response.json();
        setCurrentTLE(data);
        setLine1(data.line1);
        setLine2(data.line2);
      }
    } catch (e) {
      console.error('Failed to fetch current TLE:', e);
    }
  };

  const handleSetTLE = async () => {
    setError(null);
    setLoading(true);

    try {
      const response = await fetch('/api/simulation/tle', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ line1, line2 }),
      });

      const responseText = await response.text();

      if (!response.ok) {
        // Try to parse error as JSON, fallback to text
        let errorMessage = 'Failed to set TLE';
        try {
          const errorData = JSON.parse(responseText);
          // FastAPI validation errors have detail as array
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map((e: { msg: string }) => e.msg).join(', ');
          } else if (errorData.detail) {
            errorMessage = errorData.detail;
          }
        } catch {
          if (responseText) errorMessage = responseText;
        }
        throw new Error(errorMessage);
      }

      // Parse success response
      try {
        const data = JSON.parse(responseText);
        setCurrentTLE(data);
        setError(null);
      } catch {
        throw new Error(`Invalid JSON response from server: ${responseText.substring(0, 100)}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to set TLE');
    } finally {
      setLoading(false);
    }
  };

  const handleFetchFromCelesTrak = async () => {
    setError(null);
    setLoading(true);

    try {
      // Fetch TLE from CelesTrak by name search
      const url = `${CELESTRAK_SEARCH_URL}?NAME=${encodeURIComponent(searchQuery)}&FORMAT=TLE`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error('Failed to fetch from CelesTrak');
      }

      const text = await response.text();

      // Check for CelesTrak error responses
      if (text.includes('No GP data found') || text.includes('No TLE data')) {
        throw new Error(`Satellite "${searchQuery}" not found on CelesTrak`);
      }

      const lines = text.trim().split('\n');

      if (lines.length < 3) {
        throw new Error(`Satellite "${searchQuery}" not found on CelesTrak`);
      }

      // TLE format: Name (line 0), Line1 (line 1), Line2 (line 2)
      const fetchedLine1 = lines[1].trim();
      const fetchedLine2 = lines[2].trim();

      // Validate TLE lines start with correct characters
      if (!fetchedLine1.startsWith('1 ') || !fetchedLine2.startsWith('2 ')) {
        throw new Error('Invalid TLE format received from CelesTrak');
      }

      setLine1(fetchedLine1);
      setLine2(fetchedLine2);

      // Automatically set the TLE
      const setResponse = await fetch('/api/simulation/tle', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ line1: fetchedLine1, line2: fetchedLine2 }),
      });

      const responseText = await setResponse.text();

      if (!setResponse.ok) {
        // Try to parse error as JSON, fallback to text
        let errorMessage = 'Failed to set TLE';
        try {
          const errorData = JSON.parse(responseText);
          // FastAPI validation errors have detail as array
          if (Array.isArray(errorData.detail)) {
            errorMessage = errorData.detail.map((e: { msg: string }) => e.msg).join(', ');
          } else if (errorData.detail) {
            errorMessage = errorData.detail;
          }
        } catch {
          if (responseText) errorMessage = responseText;
        }
        throw new Error(errorMessage);
      }

      // Parse success response
      try {
        const data = JSON.parse(responseText);
        setCurrentTLE(data);
        setError(null);
      } catch {
        throw new Error(`Invalid JSON response from server: ${responseText.substring(0, 100)}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch TLE');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="tle-settings">
      <div className="panel-header" onClick={() => setCollapsed(!collapsed)}>
        <span>{collapsed ? '▶' : '▼'}</span>
        <h3>Orbit (TLE)</h3>
      </div>

      {collapsed && currentTLE && (
        <div className="tle-summary">
          {currentTLE.inclination.toFixed(1)}° / {(currentTLE.period / 60).toFixed(0)}min
        </div>
      )}

      {!collapsed && (
        <>
          {currentTLE && (
            <div className="telemetry-section">
              <h4>Current Orbit</h4>
              <p>Inclination: {currentTLE.inclination.toFixed(2)}°</p>
              <p>Period: {(currentTLE.period / 60).toFixed(1)} min</p>
            </div>
          )}

          <div className="telemetry-section">
            <h4>Fetch from CelesTrak</h4>
            <div className="tle-fetch-row">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Satellite name (e.g., AE1C)"
                disabled={!isConnected || loading}
              />
              <button
                onClick={handleFetchFromCelesTrak}
                disabled={!isConnected || loading || !searchQuery}
              >
                {loading ? 'Loading...' : 'Fetch'}
              </button>
            </div>
          </div>

          <div className="telemetry-section">
            <h4>Manual TLE Input</h4>
            <div className="tle-input">
              <label>Line 1:</label>
              <input
                type="text"
                value={line1}
                onChange={(e) => setLine1(e.target.value)}
                placeholder="1 NNNNN..."
                disabled={!isConnected || loading}
                className="tle-line-input"
              />
            </div>
            <div className="tle-input">
              <label>Line 2:</label>
              <input
                type="text"
                value={line2}
                onChange={(e) => setLine2(e.target.value)}
                placeholder="2 NNNNN..."
                disabled={!isConnected || loading}
                className="tle-line-input"
              />
            </div>
            <button
              onClick={handleSetTLE}
              disabled={!isConnected || loading || !line1 || !line2}
              className="tle-set-button"
            >
              {loading ? 'Setting...' : 'Set TLE'}
            </button>
          </div>

          {error && <div className="tle-error">{error}</div>}
        </>
      )}
    </div>
  );
}
