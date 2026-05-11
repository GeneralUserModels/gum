import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LeftPane from './LeftPane';
import Carousel from './Carousel';
import App from '../App';
import dynamicData from '../data/dynamicData.json';
import { DynamicDataProvider } from '../context/DynamicDataContext';
import { FaFileAlt, FaGithub, FaArrowDown, FaArrowUp, FaBook } from 'react-icons/fa'; // Added FaBook icon
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FaChevronLeft, FaChevronRight } from 'react-icons/fa';
import demoChat   from './pics/demo_chat.png';
import demoMemory from './pics/demo_memory.png';
import demoPopup   from './pics/demo_popup.png';
import demoSuggestions from './pics/demo_suggestions.png';



const DemoPage = () => {
  const [selectedHour, setSelectedHour] = useState(1); // Default to 1 PM
  const [abstractExpanded, setAbstractExpanded] = useState(false); // State for abstract toggle
  const [activeChats, setActiveChats] = useState([]);
  const navigate = useNavigate();
  const assetBase = import.meta.env.BASE_URL;
  const screenshots = [
    { src: demoSuggestions, caption: 'The GUMBO App is a working desktop app, displaying suggestions to users live as they use their computer.' },
    { src: demoMemory, caption: 'The Memory page allows users to view the raw propositions in their GUM, and edit, delete, or add propositions.' },
    { src: demoPopup,   caption: 'GUMBO suggestions can be accessed easily from anywhere through a popup that can be opened at the bottom left of the screen' },
    { src: demoChat,   caption: 'Hitting "Start Chat" on a suggestion gives the user more detail into the suggestion and a view of what GUMBO has already completed for the user. Users can continue the conversation with GUMBO in the chat.' },
  ];
  const [shotIdx, setShotIdx] = useState(0);
  

  // Ensure we match the key type in dynamicData (keys as strings)
  const currentData = dynamicData[selectedHour.toString()] || { carousel: [], suggestions: [], activity: "" };

  const handleTimeChange = (newHour) => {
    setSelectedHour(newHour);
    setActiveChats([]);
    navigate('/');
  };

  const toggleAbstract = () => {
    setAbstractExpanded(!abstractExpanded);
  };

  const codeString = `from dotenv import load_dotenv
load_dotenv()

import asyncio
from gum import gum
from gum.observers import Screen

async def main():
    async with gum("Omar Shaikh", Screen()):
        await asyncio.Future() # run forever (Ctrl-C to stop)

if __name__ == "__main__":
    asyncio.run(main())
`;

  return (

    <div style={{margin: '0 auto', paddingLeft: '5%', paddingRight: '5%', paddingTop: '20px', paddingBottom: '20px' }}>
      <h1 style={{ marginBottom: '20px', textAlign: 'center' }}>Creating General User Models from Computer Use</h1>
      
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', marginBottom: '10px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '0 15px', marginBottom: '15px' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: '500' }}>Omar Shaikh</div>
          <div style={{  fontWeight: '300' }}>Stanford</div>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '0 15px', marginBottom: '15px' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: '500', }}>Shardul Sapkota</div>
          <div style={{  fontWeight: '300' }}>Stanford</div>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '0 15px', marginBottom: '15px' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: '500', }}>Shan Rizvi</div>
          <div style={{  fontWeight: '300' }}>Independent</div>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '0 15px', marginBottom: '15px' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: '500'}}>Eric Horvitz</div>
          <div style={{  fontWeight: '300' }}>Microsoft</div>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '0 15px', marginBottom: '15px' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: '500' }}>Joon Sung Park</div>
          <div style={{  fontWeight: '300' }}>Stanford</div>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '0 15px', marginBottom: '15px' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: '500'}}>Diyi Yang</div>
          <div style={{  fontWeight: '300' }}>Stanford</div>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '0 15px', marginBottom: '15px' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: '500'}}>Michael S. Bernstein</div>
          <div style={{  fontWeight: '300' }}>Stanford</div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', gap: '15px', marginBottom: '20px' }}>
        <a href="https://arxiv.org/abs/2505.10831" target="_blank" rel="noopener noreferrer" className="start-chat-button" style={{ padding: '12px 12px', fontSize: '16px', display: 'flex', alignItems: 'center' }}>
          <FaFileAlt style={{ marginRight: '0.5rem', fontSize: '18px' }} /> Paper
        </a>
        
        <a href="https://github.com/generalusermodels/gum" target="_blank" rel="noopener noreferrer" className="start-chat-button" style={{ padding: '12px 12px', fontSize: '16px', display: 'flex', alignItems: 'center' }}>
          <FaGithub style={{ marginRight: '0.5rem', fontSize: '18px' }} /> GitHub
        </a>

        <a href="/gum/docs/" target="_blank" rel="noopener noreferrer" className="start-chat-button" style={{ padding: '12px 12px', fontSize: '16px', display: 'flex', alignItems: 'center' }}>
          <FaBook style={{ marginRight: '0.5rem', fontSize: '18px' }} /> Docs
        </a>
      </div>

      <div style={{
        padding: '25px 30px', 
        borderLeft: '4px solid var(--chat-button-bg)',
        borderRadius: '6px',
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)'
      }}>
        <p style={{ 
          lineHeight: '1.6',
          margin: '0',
          fontSize: '15px'
        }}>
          Human-computer interaction has long imagined technology that understands us—from our preferences and habits, to the timing and purpose of our everyday actions. Yet current user models remain fragmented, narrowly tailored to specific apps, and incapable of the flexible reasoning required to fulfill these visions. This paper presents an architecture for a general user model (GUM) that learns about you by observing any interaction you have with your computer. The GUM takes as input any unstructured observation of a user (e.g., device screenshots) and constructs confidence-weighted propositions that capture the user's knowledge and preferences.
        </p>
        {!abstractExpanded && (
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '15px' }}>
            <button 
              onClick={toggleAbstract}
              className="start-chat-button"
              style={{
                padding: '8px 16px',
                fontSize: '14px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <FaArrowDown style={{ fontSize: '12px' }} /> Expand abstract
            </button>
          </div>
        )}
        {abstractExpanded && (
          <>
            <p style={{ 
              lineHeight: '1.6',
              margin: '15px 0 0 0',
              fontSize: '15px'
            }}>
              GUMs can infer that a user is preparing for a wedding they're attending from messages with a friend. Or recognize that a user is struggling with a collaborator's feedback on a draft by observing multiple stalled edits and a switch to reading related work. GUMs introduce an architecture that infers new propositions about a user from multimodal observations, retrieves related propositions for context, and continuously revises existing propositions. To illustrate the breadth of applications that GUMs enable, we demonstrate how they augment chat-based assistants with context, manage OS notifications to selectively surface important information, and enable interactive agents that adapt to preferences across apps. We also instantiate proactive assistants (GUMBOs) that discover and execute useful suggestions on a user's behalf using their GUM. In our evaluations, we find that GUMs make calibrated and accurate inferences about users, and that assistants built on GUMs proactively identify and perform actions that users wouldn't think to request explicitly. Altogether, GUMs introduce methods that leverage multimodal models to understand unstructured context, enabling long-standing visions of HCI and entirely new interactive systems that anticipate user needs.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '15px' }}>
              <button 
                onClick={toggleAbstract}
                className="start-chat-button"
                style={{
                  padding: '8px 16px',
                  fontSize: '14px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <FaArrowUp style={{ fontSize: '12px' }} /> Collapse abstract
              </button>
            </div>
          </>
        )}
      </div>


      <div className="layout">
      <div className="left-pane">
        <LeftPane
          selectedHour={selectedHour}
          onTimeChange={handleTimeChange}
          activity={currentData.activity}
          gif={currentData.gif}
        />
      </div>

      <div className="carousel-pane">
        <Carousel carouselData={currentData.carousel} />
        <p style={{ marginTop: '0px' }}>
          Above is a collection of propositions that a GUM might make about a user based on their computer use. Drag the slider to see propositions update based on various activities during the day.
        </p>
      </div>
    </div>

      <div style={{ 
        margin: '14px 0px 0px 0px', 
        padding: '25px 30px', 
        borderLeft: '4px solid var(--chat-button-bg)',
        borderRadius: '6px',
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)'
      }}>
        <h3 style={{ 
          color: 'var(--color-main-text)', 
          margin: '0 0 15px 0',
          fontSize: '1.5em',
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center'
        }}>
          What can you build with GUMs?
        </h3>
        <p style={{ 
          lineHeight: '1.6',
          margin: '0',
          fontSize: '15px'
        }}>
          Any application that might rely on unstructured user context could benefit from a GUM. We create a new class of proactive assistants (GUMBOs) that discover and execute useful suggestions on a user's behalf based on their GUM. GUMBO discovers helpful suggestions, determines if a suggestion is worth showing to a user and executing, and then executes the (sandboxed) suggestion to the best of its ability---sharing preliminary results with the user.
        </p>
      </div>

        {/* Right Pane with the main App wrapped in the Dynamic Data Provider */}
        <div className="layout" style={{ marginTop: '5px' }}>
        <div className="left-pane">
          <LeftPane
            selectedHour={selectedHour}
            onTimeChange={handleTimeChange}
            activity={currentData.activity}
            gif={currentData.gif}
          />
        </div>
        <div className="carousel-pane">
          <DynamicDataProvider
            selectedHour={selectedHour}
            currentData={currentData}
          >
            <App
              carouselData={currentData.carousel}
              suggestionsData={currentData.suggestions}
              activeChats={activeChats}
              setActiveChats={setActiveChats}
            />
          </DynamicDataProvider>
          <p style={{ 
            marginTop: '15px',
          }}>
            Above is an example instantiation of GUMBO based on the user's current GUM. You can click on "Open Chat" to explore example interactions with suggestions. Dragging the slider will update the GUMBO's suggestions based on the user's changing GUM.  
          </p>
        </div>        
      </div>

      <div style={{ 
        margin: '14px 0px 0px 0px', 
        padding: '25px 30px', 
        borderLeft: '4px solid var(--chat-button-bg)',
        borderRadius: '6px',
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)'
      }}>
        <h3 style={{ 
          color: 'var(--color-main-text)', 
          margin: '0 0 15px 0',
          fontSize: '1.5em',
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center'
        }}>
          The GUM API
        </h3>
        <p style={{ 
          lineHeight: '1.6',
          margin: '0',
          fontSize: '15px'
        }}>
          We implement an easy-to-use Python API for GUMs. Check out the documentation on our <a href="https://github.com/generalusermodels/gum" target="_blank" rel="noopener noreferrer" style={{ color: '#ff9d9d' }}>GitHub</a> (under construction!)
        </p>
        
        <div style={{ marginTop: '15px', borderRadius: '8px', overflow: 'hidden' }}>
          <SyntaxHighlighter 
            language="python" 
            style={atomDark}
            customStyle={{ 
              borderRadius: '8px', 
              marginTop: '10px',
              fontSize: '14px',
              padding: '20px' 
            }}
          >
            {codeString}
          </SyntaxHighlighter>
        </div>

        <p style={{ 
          lineHeight: '1.6',
          // margin: '0',
          fontSize: '15px'
        }}>
          We also have an <a href="https://github.com/GeneralUserModels/gum-mcp" target="_blank" rel="noopener noreferrer" style={{ color: '#ff9d9d' }}>example</a> that connects GUMs to a Model Context Protocol, so you can easily plug a GUM into any chat-based assistant.
        </p>

        <h3 style={{ 
          color: 'var(--color-main-text)', 
          margin: '20px 0 15px 0',
          fontSize: '1.5em',
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center'
        }}>
          How it works
        </h3>
        
        <div className="flow-figure-container">
          <img 
            src={`${assetBase}final_pipeline.jpg`}
            alt="GUM Pipeline Architecture" 
            className="responsive-image"
          />
        </div>


        <p style={{ 
          lineHeight: '1.6',
          margin: '0',
          fontSize: '15px'
        }}>
          A Propose module translates unstructured observations into confidence-weighted propositions about the user's preferences, context, and intent. A Retrieve module indexes and searches these propositions to return the most contextually relevant subset for a given query. Finally, using results from Retrieve, a Revise module reevaluates and refines propositions as new observations arrive. Each module is parameterized by a large multimodal model (in our case, a vision and language model, or VLM).
        </p>

        <h3 style={{ 
          color: 'var(--color-main-text)', 
          margin: '20px 0 15px 0',
          fontSize: '1.5em',
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center'
        }}>
          Privacy
        </h3>
        <p style={{ 
          lineHeight: '1.6',
          margin: '0',
          fontSize: '15px'
        }}>
          For GUMs, privacy guarantees are critical from the start. Our general engineering principle here is to rely primarily on open-source models for our study. While closed-source models are more performant, we expect open-source models to be owned by individual users and eventually distilled to be run on local devices. Our study was deployed and run with open-source models. As gaps between closed and open-sourced models close and as models become cheaper for inference, models will become more performant and feasible on commodity hardware. Our implementation is open-source (available on <a href="https://github.com/generalusermodels/gum" target="_blank" rel="noopener noreferrer" style={{ color: '#ff9d9d' }}>GitHub</a>) and uses the OpenAI Completions API. Open-source inference platforms like vLLM support the Completions API, and work with systems like GUM.
        </p>


        <h3 style={{ 
          color: 'var(--color-main-text)', 
          margin: '20px 0 15px 0',
          fontSize: '1.5em',
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center'
        }}>
          Results
        </h3>
        <p style={{ 
          lineHeight: '1.6',
          margin: '0',
          fontSize: '15px'
        }}>
          In our technical evaluations, we first focus on validating GUM accuracy. We train GUM on recent email interactions, feeding each email---metadata, attachments, links, and replies---sequentially into the GUM. N=18 participants judged propositions generated by GUMs as overall accurate and well-calibrated: unconfident when incorrect, and confident when correct. Highly confident propositions (confidence = 10) were rated 100% accurate, while all propositions on average---including ones with low confidence---were fairly accurate (76.15%). From ablation studies, we show that all GUM components are critical for accuracy. 
          
          <div className="graph-figure-container">
            <img 
              src={`${assetBase}calibration_plot.png`}
              alt="GUM Calibration Results" 
              className="responsive-image"
            />
          </div>
          <p style={{ 
            textAlign: 'center',
            fontSize: '14px',
            color: 'var(--color-secondary-text)',
            marginTop: '10px'
          }}>
            Figure: GUMs are generally well calibrated. When errors occur, GUMs are underconfident in their propositions---the actual model's predictions lie above perfect calibration. In the user modeling setting, this is ideal. We should underestimate propositions to avoid eroding user trust.
          </p>

          We then deploy GUMBO with N=5 participants for 5 days, with the system observing the participants' screens. This longitudinal evaluation replicated our results with the underlying GUM. Additionally, participants identified a meaningful number of useful and well-executed suggestions completed by GUMBO. Two of the five participants found particularly high value in the system and asked to continue running it on their computer after the study concluded. Our evaluations also highlight limitations and boundary conditions of GUM and GUMBO, including privacy considerations and overly candid propositions. Please read our <a href="https://arxiv.org/abs/2505.10831" target="_blank" rel="noopener noreferrer" style={{ color: '#ff9d9d' }}>paper</a> for more details!

        </p>

        {/* ───────────── GUMBO Desktop App screenshots ───────────── */}
  <h3
    style={{
      color: 'var(--color-main-text)',
      margin: '20px 0 15px 0',
      fontSize: '1.5em',
      fontWeight: 600,
    }}
  >
    The GUMBO Desktop App
  </h3>
  <p
    style={{
      lineHeight: 1.6,
      margin: '0 0 20px 0',
      fontSize: '15px',
    }}
  >
    We built a fully functional macOS GUMBO client. Below are a couple of
    screenshots that showcase the interface and key features.
  </p>

  {/* screenshot carousel */}
  <section>
      <div className="app-screenshot-container">
        <button
          aria-label="Previous screenshot"
          onClick={() =>
            setShotIdx(i => (i - 1 + screenshots.length) % screenshots.length)
          }
          className="app-screenshot-arrow app-screenshot-arrow--left"
        >
          <FaChevronLeft />
        </button>

        <img
          src={screenshots[shotIdx].src}
          alt={`GUMBO screenshot ${shotIdx + 1}`}
          className="app-screenshot-image"
        />

        <button
          aria-label="Next screenshot"
          onClick={() =>
            setShotIdx(i => (i + 1) % screenshots.length)
          }
          className="app-screenshot-arrow app-screenshot-arrow--right"
        >
          <FaChevronRight />
        </button>
      </div>
    </section>
  {/* caption */}
  <p
    style={{
      textAlign: 'center',
      marginTop: '12px',
      fontSize: '14px',
      color: 'var(--color-secondary-text)',
    }}
  >
    {screenshots[shotIdx].caption}
  </p>

        
        <h3 style={{ 
          color: 'var(--color-main-text)', 
          margin: '20px 0 15px 0',
          fontSize: '1.5em',
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center'
        }}>
          Citation
        </h3>
        <div style={{ 
            position: 'relative',
            backgroundColor: 'rgba(0, 0, 0, 0.05)', 
            borderRadius: '6px',
            padding: '15px',
            fontFamily: 'monospace',
            fontSize: '14px',
            whiteSpace: 'pre-wrap',
            overflowX: 'auto'
          }}>
            <pre id="bibtex-content" style={{ margin: '0' }}>
{`@article{shaikh2025gums,
  title={Creating General User Models from Computer Use},
  author={Shaikh, Omar and Sapkota, Shardul and Rizvi, Shan and Horvitz, Eric and Park, Joon Sung and Yang, Diyi and Bernstein, Michael S.},
  journal={arXiv preprint},
  year={2025}
}`}
            </pre>
            <button 
              onClick={() => {
                navigator.clipboard.writeText(document.getElementById('bibtex-content').textContent);
                document.getElementById('copy-btn').textContent = 'Copied!';
                setTimeout(() => {
                  document.getElementById('copy-btn').textContent = 'Copy';
                }, 2000);
              }}
              id="copy-btn"
              style={{
                position: 'absolute',
                top: '10px',
                right: '10px',
                backgroundColor: 'var(--chat-button-bg)',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                padding: '6px 12px',
                fontSize: '12px',
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
            >
              Copy
            </button>
          </div>
        </div>
      </div>
  );
};

export default DemoPage;
