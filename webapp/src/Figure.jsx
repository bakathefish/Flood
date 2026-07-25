import React from 'react';
import {VStack} from '@astryxdesign/core/VStack';
import {Text} from '@astryxdesign/core/Text';

// image + caption, used for the evidence figures
export default function Figure({src, alt, tag, caption}) {
  return (
    <VStack gap={2}>
      <img
        src={src}
        alt={alt}
        loading="lazy"
        style={{width: '100%', height: 'auto', display: 'block', border: '1px solid var(--color-border-emphasized)', borderRadius: 'var(--radius-inner, 2px)', background: '#0e1114'}}
      />
      {(tag || caption) && (
        <Text type="supporting" color="secondary">
          {tag ? <Text type="supporting" color="accent">{tag} </Text> : null}
          {caption}
        </Text>
      )}
    </VStack>
  );
}
