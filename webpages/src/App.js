import logo from './logo.svg';
import './App.css';
import React, { Component }  from 'react';

import { Button, Space } from 'antd';
import 'antd/dist/reset.css'

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
        <p>
          Edit <code>src/App.js</code> and save to reload.
        </p>
        <a
          className="App-link"
          href="https://reactjs.org"
          target="_blank"
          rel="noopener noreferrer"
        >
          Learn React
        </a>
      </header>
      <Button type="primary">Primary Button</Button>
    </div>
  );
}

export default App;
