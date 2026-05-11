import React from 'react';
import { Link } from 'react-router-dom';
import { FaComments } from 'react-icons/fa'; // import the icon

const SuggestionItem = ({ suggestion }) => {
  return (
    <div className="suggestion-item">
      <h3 className="suggestion-title">{suggestion.title}</h3>
      <p className="suggestion-description">{suggestion.description}</p>
      
      <Link to={`/chat/${suggestion.id}`} className="start-chat-button">
        <FaComments style={{ marginRight: '0.3rem', position: 'relative', top: '1px' }} /> Open Chat
      </Link>
    </div>
  );
};

export default SuggestionItem;
