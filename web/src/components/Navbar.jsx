import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

const Navbar = ({ activeChats, isMobile, onClose }) => {
  const location = useLocation();
  const [sidebarWidth, setSidebarWidth] = useState(250);

  /* ---------- desktop‑only drag‑resize ---------- */
  const handleMouseMove = (e) => {
    const newWidth = Math.max(e.clientX, 180); // min 180 px
    setSidebarWidth(newWidth);
  };
  const stopResize = () => {
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', stopResize);
  };
  const startResize = (e) => {
    if (isMobile) return;
    e.preventDefault();
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', stopResize);
  };

  /* ---------- positioning ---------- */
  const navStyle = isMobile
    ? {
        width: sidebarWidth,
        position: 'absolute',
        top: 0,
        left: 0,
        height: '100%',
        /* NOTHING ELSE OVERRIDDEN → inherits the same background,
           padding, fonts, etc., as the desktop bar */
        zIndex: 15,
      }
    : {
        width: sidebarWidth,
        position: 'relative',
      };

  return (
    <div className="navbar" style={navStyle}>
      {/* mobile close (×) */}
      {isMobile && (
        <button
          aria-label="Close sidebar"
          onClick={onClose}
          style={{
            position: 'absolute',
            top: 10,
            right: 10,
            background: 'none',
            border: 'none',
            fontSize: '1.8rem',
            color: '#d6ceba',
            cursor: 'pointer',
          }}
        >
          &times;
        </button>
      )}

      {/* suggestions link */}
      <div style={{ marginBottom: 20, marginTop: isMobile ? 50 : 0 }}>
        <Link
          to="/"
          className={`nav-link ${
            location.pathname === '/' ? 'nav-link-active' : ''
          }`}
        >
          Suggestions
        </Link>
      </div>

      {/* active chats */}
      <div style={{ fontSize: '.8rem', marginBottom: 10 }}>Active Chats</div>
      <ul style={{ listStyle: 'none', paddingLeft: 0, margin: 0 }}>
        {activeChats.map((chat) => {
          const isActive = location.pathname === `/chat/${chat.id}`;
          return (
            <li key={chat.id} style={{ marginBottom: 8 }}>
              <Link
                to={`/chat/${chat.id}`}
                className={`nav-link ${isActive ? 'nav-link-active' : ''}`}
              >
                {chat.title}
              </Link>
            </li>
          );
        })}
      </ul>

      {/* desktop resizer handle */}
      {!isMobile && (
        <div
          className="resizer"
          onMouseDown={startResize}
          style={{
            width: 2,
            cursor: 'col-resize',
            position: 'absolute',
            top: 0,
            right: 0,
            bottom: 0,
            background: '#444',
          }}
        />
      )}
    </div>
  );
};

export default Navbar;
