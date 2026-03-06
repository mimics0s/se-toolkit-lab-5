import React, { useState } from 'react';
import './App.css';
import Items from './Items';
import Dashboard from './Dashboard';

function App() {
  const [currentPage, setCurrentPage] = useState<'items' | 'dashboard'>('items');

  return (
    <div className="App">
      <nav style={{ 
        padding: '10px', 
        backgroundColor: '#f0f0f0', 
        borderBottom: '1px solid #ccc',
        display: 'flex',
        gap: '10px',
        justifyContent: 'center'
      }}>
        <button 
          onClick={() => setCurrentPage('items')}
          style={{
            padding: '8px 16px',
            backgroundColor: currentPage === 'items' ? '#007bff' : '#f8f9fa',
            color: currentPage === 'items' ? 'white' : 'black',
            border: '1px solid #007bff',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Items
        </button>
        <button 
          onClick={() => setCurrentPage('dashboard')}
          style={{
            padding: '8px 16px',
            backgroundColor: currentPage === 'dashboard' ? '#007bff' : '#f8f9fa',
            color: currentPage === 'dashboard' ? 'white' : 'black',
            border: '1px solid #007bff',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Dashboard
        </button>
      </nav>

      <main>
        {currentPage === 'items' ? <Items /> : <Dashboard />}
      </main>
    </div>
  );
}

export default App;