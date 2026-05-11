import React from 'react';
import SuggestionItem from './SuggestionItem';

const SuggestionsPage = ({ suggestionsData }) => {
  return (
    
    <div
      className="page-content"
      style={{
        padding: 0,
        backgroundColor: '#282828',
        // maxHeight: '500px',
        overflow: 'scroll'
      }}
    >
      {/* Title Section */}
      <div
        style={{
          padding: '30px 0 10px 5%'
        }}
      >
        <h1
          style={{
            fontSize: 25,
            fontWeight: 'bold',
            marginLeft: 20,
            color: '#d6ceba',
            paddingBottom: 10
          }}
        >
          Suggestions
        </h1>
      </div>

      {/* Suggestions List */}
      {suggestionsData.map((suggestion) => (
        <div key={suggestion.id} style={{ width: '85%', margin: '0 auto 20px' }}>
          <SuggestionItem suggestion={suggestion} />
        </div>
      ))}
    </div>
  );
};

export default SuggestionsPage;
