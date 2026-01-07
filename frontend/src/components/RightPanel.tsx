import { useState } from 'react';
import './RightPanel.css';

interface RightPanelProps {
  children: React.ReactNode;
  title: string;
  defaultCollapsed?: boolean;
}

export function RightPanel({ children, title, defaultCollapsed = true }: RightPanelProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  const toggleCollapsed = () => {
    setCollapsed(!collapsed);
  };

  return (
    <aside className={`right-panel ${collapsed ? 'collapsed' : 'expanded'}`}>
      {collapsed ? (
        <div className="right-panel-tab" onClick={toggleCollapsed}>
          <span className="right-panel-tab-icon">◀</span>
          <span className="right-panel-tab-title">{title}</span>
        </div>
      ) : (
        <>
          <div className="right-panel-header" onClick={toggleCollapsed}>
            <span className="right-panel-title">{title}</span>
            <span className="right-panel-collapse-icon">▶</span>
          </div>
          <div className="right-panel-content">
            {children}
          </div>
        </>
      )}
    </aside>
  );
}
