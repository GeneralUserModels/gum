import React, { createContext, useContext } from 'react';

const DynamicDataContext = createContext();

export const useDynamicData = () => useContext(DynamicDataContext);

export const DynamicDataProvider = ({ selectedHour, currentData, children }) => {
  return (
    <DynamicDataContext.Provider value={{ selectedHour, currentData }}>
      {children}
    </DynamicDataContext.Provider>
  );
};

export default DynamicDataContext;
