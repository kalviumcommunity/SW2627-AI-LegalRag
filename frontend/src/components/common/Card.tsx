import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  padding = 'md',
  style,
  ...rest
}) => {
  const paddingMap = {
    none: '0',
    sm: '1rem',
    md: '1.5rem',
    lg: '2rem',
  };

  return (
    <div
      className={`editorial-card ${className}`}
      style={{
        padding: paddingMap[padding],
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
};
