import React, {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  forwardRef,
} from 'react';

/* ─────────────────────────  ROW  ───────────────────────── */

const AnimatedRow = forwardRef(({ row, rowIndex }, rowContainerRef) => (
  <div
    style={{
      position: 'relative',
      overflow: 'hidden',
      marginBottom: '15px',
    }}
  >
    <div
      ref={rowContainerRef}
      style={{
        display: 'flex',
        animation: 'marquee var(--animation-duration) linear infinite',
      }}
    >
      {/* ORIGINAL SET */}
      {row.map((card, i) => {
        const isFirstCardInSecondRow = rowIndex === 1 && i === 0;
        return (
          <div
            key={card.id}
            style={{
              position: 'relative',
              marginRight: '20px',
              flex: '0 0 275px',
              marginLeft: isFirstCardInSecondRow ? '132px' : '0',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: '4px',
                fontSize: '12px',
                marginLeft: '6px',
                marginRight: '6px',
                color: 'var(--color-main-text)',
                opacity: 0.7,
              }}
            >
              <span>Proposition</span>
              <span>Confidence</span>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                backgroundColor: 'var(--color-main-text)',
                borderRadius: '8px',
                padding: '10px 0 6px 12px',
                height: '60px',
                boxSizing: 'border-box',
              }}
            >
              <div
                style={{
                  width: '210px',
                  color: '#333',
                  fontFamily: 'sans-serif',
                  fontSize: '16px',
                  lineHeight: 1.2,
                  height: '40px',
                  overflow: 'hidden',
                }}
              >
                {card.text}
              </div>
              <div
                style={{
                  width: '1px',
                  backgroundColor: '#888888',
                  height: '40px',
                  margin: '0 2px 0 10px',
                }}
              />
              <div
                style={{
                  flex: 1,
                  fontWeight: 'bold',
                  fontSize: '17px',
                  color: '#333',
                  textAlign: 'center',
                }}
              >
                {card.value}
              </div>
            </div>
          </div>
        );
      })}

      {/* DUPLICATE SET (for seamless loop) */}
      {row.map((card) => (
        <div
          key={`${card.id}-dup`}
          style={{
            position: 'relative',
            marginRight: '20px',
            flex: '0 0 275px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginBottom: '4px',
              marginLeft: '6px',
              marginRight: '6px',
              fontSize: '12px',
              color: 'var(--color-main-text)',
              opacity: 0.7,
            }}
          >
            <span>Proposition</span>
            <span>Confidence</span>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: 'var(--color-main-text)',
              borderRadius: '8px',
              padding: '10px 0 6px 12px',
              height: '60px',
              boxSizing: 'border-box',
            }}
          >
            <div
              style={{
                width: '200px',
                color: '#333',
                fontFamily: 'sans-serif',
                fontSize: '16px',
                lineHeight: 1.2,
                height: '40px',
                overflow: 'hidden',
              }}
            >
              {card.text}
            </div>
            <div
              style={{
                width: '1px',
                backgroundColor: '#888888',
                height: '60px',
                margin: '0 2px',
              }}
            />
            <div
              style={{
                flex: 1,
                fontWeight: 'bold',
                fontSize: '17px',
                color: '#333',
                textAlign: 'center',
              }}
            >
              {card.value}
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
));

/* ─────────────────────────  CAROUSEL  ───────────────────────── */

const Carousel = ({ carouselData }) => {
  const [screenWidth, setScreenWidth] = useState(window.innerWidth);
  const [startOffset, setStartOffset] = useState('-50%');
  const [rowWidth, setRowWidth] = useState(null);          // store single-set width
  const firstRowRef = useRef(null);

  /* 1️⃣  Handle viewport resize */
  useEffect(() => {
    const handleResize = () => setScreenWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  /* 2️⃣  Compute offset + remember real row width for small screens */
  useLayoutEffect(() => {
    if (screenWidth < 1000 && firstRowRef.current) {
      const totalTrackWidth = firstRowRef.current.scrollWidth;     // both copies
      const singleSetWidth = totalTrackWidth / 2;
      setRowWidth(singleSetWidth);                                 // ← remember
      const px = Math.max(singleSetWidth - screenWidth, 0);
      setStartOffset(`-${px}px`);
    } else {
      setRowWidth(null);
      setStartOffset('-50%');
    }
  }, [screenWidth, carouselData]);

  /* 3️⃣  Duration: unchanged for >1000 px; slower formula for <1000 px */
  let animationDuration = Math.max(8, screenWidth / 80);           // original rule
  if (screenWidth < 1000 && rowWidth) {
    animationDuration = Math.max(20, rowWidth / 80);               // ⇢ slower
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        padding: 0,
        boxSizing: 'border-box',
        '--animation-duration': `${animationDuration}s`,
        '--marquee-start': startOffset,
      }}
    >
      <style>{`
        @keyframes marquee {
          0%   { transform: translateX(var(--marquee-start)); }
          100% { transform: translateX(0); }
        }
      `}</style>

      <h3
        style={{
          color: 'var(--color-main-text)',
          textAlign: 'left',
          marginBottom: '12px',
          fontSize: '1.5em',
        }}
      >
        GUMs learn a wide range of preferences from unstructured interaction
      </h3>

      {carouselData.map((row, idx) => (
        <AnimatedRow
          key={idx}
          row={row}
          rowIndex={idx}
          ref={idx === 0 ? firstRowRef : null}
        />
      ))}
    </div>
  );
};

export default Carousel;
