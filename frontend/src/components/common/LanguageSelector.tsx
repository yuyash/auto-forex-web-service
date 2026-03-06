import { useState } from 'react';
import {
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Tooltip,
} from '@mui/material';
import LanguageIcon from '@mui/icons-material/Language';
import CheckIcon from '@mui/icons-material/Check';
import { useTranslation } from 'react-i18next';
import type { SxProps, Theme } from '@mui/material';
import { useAuth } from '../../contexts/AuthContext';

interface LanguageSelectorProps {
  buttonSize?: 'small' | 'medium' | 'large';
  buttonSx?: SxProps<Theme>;
}

const LanguageSelector = ({
  buttonSize = 'small',
  buttonSx,
}: LanguageSelectorProps) => {
  const { i18n, t } = useTranslation('common');
  const { token } = useAuth();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLanguageChange = (language: string) => {
    i18n.changeLanguage(language);
    handleClose();
    // Persist to backend user settings if authenticated
    if (token) {
      fetch('/api/accounts/settings/', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ language }),
      }).catch(() => {
        // Silently ignore — localStorage is the primary store
      });
    }
  };

  const languages = [
    { code: 'en', label: t('language.english') },
    { code: 'ja', label: t('language.japanese') },
  ];

  return (
    <>
      <Tooltip title={t('language.selectLanguage')}>
        <IconButton
          onClick={handleClick}
          size={buttonSize}
          aria-controls={open ? 'language-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
          color="inherit"
          sx={buttonSx}
        >
          <LanguageIcon />
        </IconButton>
      </Tooltip>
      <Menu
        id="language-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{
          'aria-labelledby': 'language-button',
        }}
      >
        {languages.map((language) => (
          <MenuItem
            key={language.code}
            onClick={() => handleLanguageChange(language.code)}
            selected={i18n.language === language.code}
          >
            <ListItemIcon>
              {i18n.language === language.code && (
                <CheckIcon fontSize="small" />
              )}
            </ListItemIcon>
            <ListItemText>{language.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
};

export default LanguageSelector;
