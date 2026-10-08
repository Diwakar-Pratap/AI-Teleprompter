import React from "react";
import Overlay from "./components/Overlay/Overlay";

const App: React.FC = () => {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column" }}>
      <Overlay />
    </div>
  );
};

export default App;
