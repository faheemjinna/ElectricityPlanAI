import React, { useState, useEffect } from "react";

function App() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch("/company")
      .then((res) => res.json())
      .then((data) => {
        setData(data);
        console.log(data);
      });
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Electricity Plan Estimator</h1>
      </header>
    </div>
  );
}

export default App;
