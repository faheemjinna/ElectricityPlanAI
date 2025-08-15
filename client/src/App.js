import React, { useState } from "react";

function App() {
  const [typeInput, setTypeInput] = useState("");
  const [companyInput, setCompanyInput] = useState("");
  const [usage, setUsage] = useState("");
  const [data, setData] = useState([]);

  const handleSubmit = (e) => {
    e.preventDefault(); // Prevent page reload

    if (!typeInput || !companyInput || !usage) {
      alert("Please fill in all fields");
      return;
    }

    // Convert usage to URL-encoded string
    const queryString = new URLSearchParams({
      type_input: typeInput,
      company_input: companyInput,
      usage: usage,
    }).toString();

    fetch(`/getestimate?${queryString}`)
      .then((res) => res.json())
      .then((data) => {
        setData(data);
        console.log(data);
      })
      .catch((err) => console.error(err));
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Electricity Plan Estimator</h1>
      </header>

      <form onSubmit={handleSubmit}>
        <div>
          <label>Type Input:</label>
          <input
            type="text"
            placeholder="e.g., apartment"
            value={typeInput}
            onChange={(e) => setTypeInput(e.target.value)}
          />
        </div>

        <div>
          <label>Company Input:</label>
          <input
            type="number"
            placeholder="e.g., 2"
            value={companyInput}
            onChange={(e) => setCompanyInput(e.target.value)}
          />
        </div>

        <div>
          <label>Usage (comma separated):</label>
          <input
            type="text"
            placeholder="e.g., 100,150,200,..."
            value={usage}
            onChange={(e) => setUsage(e.target.value)}
          />
        </div>

        <button type="submit">Get Estimate</button>
        {/* <button type="submit">Update The Link</button> */}
      </form>

      <div>
        <h2>API Response:</h2>
        <pre>{JSON.stringify(data, null, 2)}</pre>
      </div>
    </div>
  );
}

export default App;
